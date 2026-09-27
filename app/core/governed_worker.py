from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Callable

from app.core.automation_control_plane import automation_control_plane
from app.core.automation_queue import AutomationQueue, automation_queue
from app.core.automation_runtime import AutomationRuntime, automation_runtime
from app.core.execution.authorization import execution_authorization
from app.core.execution.runtime import canonical_execution_runtime
from app.core.execution_ledger import ExecutionLedger, execution_ledger
from app.core.execution_telemetry import execution_telemetry
from app.core.automation_outcome_service import automation_outcome_service
from app.core.execution_evidence import execution_evidence
from app.core.golden_workflow_trace import golden_workflow_trace
from app.core.worker_coordination import WorkerCoordinator, worker_coordinator


@dataclass(frozen=True)
class WorkerResult:
    status: str
    job_id: int | None = None
    executed: bool = False
    detail: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"status": self.status, "job_id": self.job_id,
                "executed": self.executed, "detail": self.detail or {}}


class GovernedWorker:
    VERSION = "4.0"

    def __init__(self, queue: AutomationQueue | None = None,
                 runtime: AutomationRuntime | None = None,
                 coordinator: WorkerCoordinator | None = None,
                 ledger: ExecutionLedger | None = None) -> None:
        self.queue = queue or automation_queue
        self.runtime = runtime or automation_runtime
        self.coordinator = coordinator or worker_coordinator
        self._uses_injected_queue = queue is not None
        self._uses_injected_runtime = runtime is not None
        self.ledger = ledger or execution_ledger

    def process_one(self, *, worker_id: str,
                    plan_resolver: Callable[[dict[str, Any]], Any],
                    lease_seconds: int = 60,
                    organization_id: int | None = None,
                    job_id: int | None = None,
                    org_limit: int = WorkerCoordinator.DEFAULT_ORG_LIMIT,
                    global_limit: int = WorkerCoordinator.DEFAULT_GLOBAL_LIMIT) -> dict[str, Any]:
        claimed = self.queue.claim(
            worker_id=worker_id, lease_seconds=lease_seconds,
            organization_id=organization_id, job_id=job_id,
        )
        if not claimed:
            return WorkerResult(status="idle").as_dict()
        job_id = int(claimed["job_id"])
        payload = claimed["payload"]
        organization_id = claimed.get("organization_id")
        execution_key = str(claimed.get("job_key") or job_id)
        if organization_id is not None:
            execution_evidence.record(
                organization_id=int(organization_id), execution_key=execution_key,
                job_id=job_id, event_id=payload.get("event_id"),
                workflow_id=payload.get("workflow_id"), stage="queue.claimed",
                status="claimed", worker_id=worker_id,
                correlation_id=payload.get("correlation_id"), trace_id=payload.get("trace_id"),
                evidence_key=f"{execution_key}:queue.claimed",
                receipt={"attempt": claimed.get("attempt")},
            )
        if organization_id is not None:
            admission = self.coordinator.admit(
                organization_id=int(organization_id), current_job_id=job_id,
                org_limit=org_limit, global_limit=global_limit,
            )
            if not admission["allowed"]:
                failure = self.queue.fail(job_id, admission["reason"], worker_id=worker_id)
                self._terminal_evidence(
                    organization_id=int(organization_id), execution_key=execution_key,
                    job_id=job_id, payload=payload, worker_id=worker_id,
                    status="concurrency_limited", reason=admission["reason"],
                )
                return WorkerResult(status="concurrency_limited", job_id=job_id,
                                    detail={"admission": admission, "queue": failure}).as_dict()
        if not self._uses_injected_queue and self.coordinator.is_cancelled(job_id=job_id, worker_id=worker_id):
            self.queue.cancel(job_id, worker_id=worker_id)
            if organization_id is not None:
                self._terminal_evidence(
                    organization_id=int(organization_id), execution_key=execution_key,
                    job_id=job_id, payload=payload, worker_id=worker_id, status="cancelled",
                    reason="cooperative_cancellation",
                )
            return WorkerResult(status="cancelled", job_id=job_id).as_dict()
        deadline_at = claimed.get("deadline_at")
        if deadline_at and time.time() >= _timestamp(deadline_at):
            failure = self.queue.fail(job_id, "execution_deadline_exceeded", worker_id=worker_id)
            if organization_id is not None:
                self._terminal_evidence(
                    organization_id=int(organization_id), execution_key=execution_key,
                    job_id=job_id, payload=payload, worker_id=worker_id,
                    status="deadline_exceeded", reason="execution_deadline_exceeded",
                )
            return WorkerResult(status="deadline_exceeded", job_id=job_id,
                                 detail={"queue": failure}).as_dict()
        durable_plan = payload.get("execution_plan")
        durable_authorization = payload.get("authorization")
        durable_mode = durable_plan is not None or durable_authorization is not None
        if durable_mode:
            if not isinstance(durable_plan, dict) or not isinstance(durable_authorization, dict):
                failure = self.queue.fail(job_id, "durable_execution_envelope_invalid", worker_id=worker_id, retryable=False)
                if organization_id is not None:
                    self._terminal_evidence(organization_id=int(organization_id), execution_key=execution_key, job_id=job_id, payload=payload, worker_id=worker_id, status="blocked", reason="durable_execution_envelope_invalid")
                return WorkerResult(status="blocked", job_id=job_id, detail={"error": "durable_execution_envelope_invalid", "queue": failure}).as_dict()
            durable_action = str(durable_plan.get("action") or "").strip()
            identity_error = _validate_durable_identity(
                plan=durable_plan, payload=payload, claimed=claimed,
                organization_id=organization_id, job_id=job_id,
            )
            if identity_error:
                failure = self.queue.fail(job_id, identity_error, worker_id=worker_id, retryable=False)
                if organization_id is not None:
                    self._terminal_evidence(
                        organization_id=int(organization_id), execution_key=execution_key,
                        job_id=job_id, payload=payload, worker_id=worker_id,
                        status="blocked", reason=identity_error,
                    )
                return WorkerResult(status="blocked", job_id=job_id, detail={"error": identity_error, "queue": failure}).as_dict()
            verification = execution_authorization.verify(durable_authorization, durable_plan, durable_action)
            if not verification.get("authorized"):
                reason = str(verification.get("error") or "durable_execution_authorization_denied")
                failure = self.queue.fail(job_id, reason, worker_id=worker_id, retryable=False)
                if organization_id is not None:
                    self._terminal_evidence(organization_id=int(organization_id), execution_key=execution_key, job_id=job_id, payload=payload, worker_id=worker_id, status="blocked", reason=reason, plan_hash=str(durable_authorization.get("plan_hash") or "") or None)
                return WorkerResult(status="blocked", job_id=job_id, detail={"error": reason, "queue": failure}).as_dict()
            plan = durable_plan
            authorization = durable_authorization
        else:
            authorization = payload.get("authorization")
            try:
                plan = plan_resolver(payload)
            except Exception:
                failure = self.queue.fail(job_id, "plan_resolution_failed", worker_id=worker_id)
                if organization_id is not None:
                    self._terminal_evidence(
                        organization_id=int(organization_id), execution_key=execution_key,
                        job_id=job_id, payload=payload, worker_id=worker_id,
                        status="failed", reason="plan_resolution_failed",
                    )
                return WorkerResult(status="failed", job_id=job_id,
                                     detail={"error": "plan_resolution_failed", "queue": failure}).as_dict()
        if plan is None:
            failure = self.queue.fail(job_id, "plan_missing", worker_id=worker_id)
            if organization_id is not None:
                self._terminal_evidence(
                    organization_id=int(organization_id), execution_key=execution_key,
                    job_id=job_id, payload=payload, worker_id=worker_id,
                    status="blocked", reason="plan_missing",
                )
            return WorkerResult(status="blocked", job_id=job_id,
                                 detail={"error": "plan_missing", "queue": failure}).as_dict()
        if not self._uses_injected_queue and self.coordinator.is_cancelled(job_id=job_id, worker_id=worker_id):
            self.queue.cancel(job_id, worker_id=worker_id)
            if organization_id is not None:
                self._terminal_evidence(
                    organization_id=int(organization_id), execution_key=execution_key,
                    job_id=job_id, payload=payload, worker_id=worker_id, status="cancelled",
                    reason="cooperative_cancellation",
                )
            return WorkerResult(status="cancelled", job_id=job_id).as_dict()

        execution_key = str(claimed.get("job_key") or job_id)
        ledger_record = None
        if organization_id is not None:
            if durable_mode:
                compiled = {"success": True, "status": "ready", "plan": plan, "plan_hash": str(authorization.get("plan_hash") or execution_authorization.plan_hash(plan)), "validation": {"valid": True}}
            else:
                compiled = automation_control_plane.compile(plan)
            if not compiled.get("success"):
                failure = self.queue.fail(job_id, "plan_compile_failed", worker_id=worker_id)
                self._terminal_evidence(
                    organization_id=int(organization_id), execution_key=execution_key,
                    job_id=job_id, payload=payload, worker_id=worker_id,
                    status="blocked", reason="plan_compile_failed",
                )
                return WorkerResult(status="blocked", job_id=job_id,
                                     detail={"compile": compiled, "queue": failure}).as_dict()
            from app.services.execution_entitlement_service import execution_entitlement_service
            entitlement = execution_entitlement_service.check(
                int(organization_id), execution_key=execution_key
            )
            if not entitlement.get("allowed"):
                failure = self.queue.fail(
                    job_id, entitlement.get("reason", "execution_not_entitled"),
                    worker_id=worker_id,
                )
                self._terminal_evidence(
                    organization_id=int(organization_id), execution_key=execution_key,
                    job_id=job_id, payload=payload, worker_id=worker_id,
                    status="commercially_blocked", reason=entitlement.get("reason", "execution_not_entitled"),
                    plan_hash=str(compiled["plan_hash"]),
                )
                return WorkerResult(
                    status="commercially_blocked", job_id=job_id,
                    detail={"entitlement": entitlement, "queue": failure},
                ).as_dict()
            approval_hash = _approval_hash(payload.get("authorization"))
            started = self.ledger.begin(
                organization_id=int(organization_id), execution_key=execution_key,
                plan_hash=str(compiled["plan_hash"]), job_id=job_id, worker_id=worker_id,
                approval_hash=approval_hash,
                decision_hash=_decision_hash(authorization),
                approval_id=payload.get("approval_id"),
                trace_id=payload.get("trace_id"),
                correlation_id=payload.get("correlation_id"),
            )
            ledger_record = started["record"]
            if not started["created"]:
                blocked_status = "idempotent_replay_blocked" if started["status"] == "completed" else "execution_in_progress"
                self.queue.cancel(job_id, worker_id=worker_id)
                self._terminal_evidence(
                    organization_id=int(organization_id), execution_key=execution_key,
                    job_id=job_id, payload=payload, worker_id=worker_id,
                    status=blocked_status, reason=f"ledger_{started['status']}",
                    plan_hash=str(compiled["plan_hash"]),
                )
                return WorkerResult(status=blocked_status, job_id=job_id,
                                    detail={"ledger": ledger_record}).as_dict()
            execution_evidence.record(
                organization_id=int(organization_id), execution_key=execution_key,
                job_id=job_id, event_id=payload.get("event_id"),
                workflow_id=payload.get("workflow_id"), stage="ledger.started",
                status="started", worker_id=worker_id,
                plan_hash=str(compiled["plan_hash"]),
                correlation_id=payload.get("correlation_id"), trace_id=payload.get("trace_id"),
                evidence_key=f"{execution_key}:ledger.started",
                receipt={
                    "ledger_id": ledger_record.get("id") if ledger_record else None,
                    "commercial_entitlement": {
                        "plan": entitlement.get("plan"),
                        "limit": entitlement.get("limit"),
                        "used_before": entitlement.get("used"),
                        "remaining_after_reservation": entitlement.get("remaining"),
                    },
                },
            )
        outcome_started_at = time.time()
        telemetry_attributes = {
            "kemet.organization_id": organization_id,
            "kemet.job_id": job_id,
            "kemet.execution_key": execution_key,
            "kemet.plan_hash": compiled.get("plan_hash") if organization_id is not None else None,
            "kemet.worker_id": worker_id,
            "kemet.trace_id": claimed.get("payload", {}).get("trace_id"),
            "kemet.correlation_id": claimed.get("payload", {}).get("correlation_id"),
        }
        with execution_telemetry.span("kemet.execution", attributes=telemetry_attributes):
            execution_telemetry.event("execution.started", attributes=telemetry_attributes)
            try:
                if durable_mode:
                    from app.automation.action_registry import registry
                    result = canonical_execution_runtime.execute(
                        plan=plan, authorization=authorization, action_registry=registry,
                        user_id=(plan.get("parameters") or {}).get("user_id") or payload.get("actor_id") or worker_id,
                        execution_envelope_payload=authorization.get("execution_envelope"),
                    )
                else:
                    if self._uses_injected_runtime:
                        result = self.runtime.execute(
                            plan, authorization=authorization,
                            actor_id=str(payload.get("actor_id") or worker_id),
                            execution_key=execution_key,
                            deadline_at=_timestamp(deadline_at) if deadline_at else None,
                        )
                    else:
                        from app.automation.action_registry import registry
                        canonical_plan = _legacy_plan_to_canonical(plan, execution_key=execution_key)
                        canonical_authorization = authorization if isinstance(authorization, dict) else {}
                        result = canonical_execution_runtime.execute(
                            plan=canonical_plan,
                            authorization=canonical_authorization,
                            action_registry=registry,
                            user_id=str(payload.get("actor_id") or worker_id),
                            execution_envelope_payload=canonical_authorization.get("execution_envelope"),
                        )
            except Exception:
                execution_telemetry.event("execution.failed", attributes={"kemet.error_type": "runtime_exception"})
                if organization_id is not None:
                    automation_outcome_service.record(
                        organization_id=int(organization_id), status="failed", executed=False,
                        job_id=job_id, workflow_id=payload.get("workflow_id"), event_id=payload.get("event_id"),
                        retry_count=max(0, int(claimed.get("attempt", 1)) - 1),
                        correlation_id=payload.get("correlation_id"), trace_id=payload.get("trace_id"),
                        started_at=_datetime_from_epoch(outcome_started_at),
                        error_type="runtime_exception", receipt={"error": "runtime_exception"},
                    )
                    self._terminal_evidence(
                        organization_id=int(organization_id), execution_key=execution_key,
                        job_id=job_id, payload=payload, worker_id=worker_id,
                        status="failed", reason="runtime_exception",
                        plan_hash=compiled.get("plan_hash"),
                    )
                    self.ledger.finish(organization_id=int(organization_id), execution_key=execution_key,
                                       status="failed", receipt={"error": "runtime_exception"})
                failure = self.queue.fail(job_id, "runtime_exception", worker_id=worker_id)
                return WorkerResult(status="failed", job_id=job_id,
                                     detail={"error": "runtime_exception", "queue": failure}).as_dict()
            status = str(result.get("execution_status") or result.get("status") or "execution_failed")
            business_status = result.get("business_status")
            execution_telemetry.event(
                "execution.completed" if status == "completed" else "execution.finished",
                attributes={"kemet.status": status, "kemet.business_status": business_status, "kemet.executed": bool(result.get("executed"))},
            )

        completion_evidence = None
        if organization_id is not None:
            outcome = automation_outcome_service.record(
                organization_id=int(organization_id), status=status, executed=bool(result.get("executed")),
                job_id=job_id, workflow_id=payload.get("workflow_id"), event_id=payload.get("event_id"),
                retry_count=max(0, int(claimed.get("attempt", 1)) - 1),
                started_at=_datetime_from_epoch(outcome_started_at),
                cost_amount=_numeric(result.get("cost_amount")),
                currency=result.get("currency"),
                correlation_id=payload.get("correlation_id"), trace_id=payload.get("trace_id"),
                business_outcome=result.get("business_outcome"), receipt={**(result.get("receipt") or result), "execution_identity": {
                    "execution_key": execution_key,
                    "job_id": job_id,
                    "workflow_id": payload.get("workflow_id"),
                    "decision_hash": _decision_hash(authorization),
                    "approval_id": payload.get("approval_id"),
                }},
                error_type=result.get("error_type") or (str(result.get("error")) if result.get("error") else None),
            )
            ledger_status = "completed" if status == "completed" else status
            receipt = result.get("receipt") or result
            self.ledger.finish(organization_id=int(organization_id), execution_key=execution_key,
                               status=ledger_status, receipt=receipt)
            execution_evidence.record(
                organization_id=int(organization_id), execution_key=execution_key,
                job_id=job_id, event_id=payload.get("event_id"),
                workflow_id=payload.get("workflow_id"), stage="outcome.recorded",
                status=status, worker_id=worker_id,
                plan_hash=compiled.get("plan_hash"),
                correlation_id=payload.get("correlation_id"), trace_id=payload.get("trace_id"),
                evidence_key=f"{execution_key}:outcome:{outcome['outcome_id']}",
                receipt={"outcome_id": outcome["outcome_id"], "executed": bool(result.get("executed"))},
            )
            completion_evidence = execution_evidence.record(
                organization_id=int(organization_id), execution_key=execution_key,
                job_id=job_id, event_id=payload.get("event_id"),
                workflow_id=payload.get("workflow_id"), stage="runtime.finished",
                status=status, worker_id=worker_id,
                plan_hash=compiled.get("plan_hash"),
                correlation_id=payload.get("correlation_id"), trace_id=payload.get("trace_id"),
                evidence_key=f"{execution_key}:runtime.finished",
                receipt={**receipt, "execution_identity": {
                    "execution_key": execution_key,
                    "job_id": job_id,
                    "workflow_id": payload.get("workflow_id"),
                    "decision_hash": _decision_hash(authorization),
                    "approval_id": payload.get("approval_id"),
                }},
            )
        if organization_id is not None and payload.get("execution_id"):
            _sync_automation_execution(
                execution_id=payload.get("execution_id"),
                workflow_id=payload.get("workflow_id"),
                organization_id=int(organization_id),
                status=status,
                result=result,
            )
        if status == "completed":
            completed = self.queue.complete(
                job_id, worker_id=worker_id,
                metadata={
                    "plan_hash": compiled.get("plan_hash") if organization_id is not None else None,
                    "decision_hash": _decision_hash(authorization),
                    "approval_id": payload.get("approval_id"),
                    "evidence_id": completion_evidence.get("id") if completion_evidence else None,
                },
            )
            if organization_id is not None:
                execution_evidence.record(
                    organization_id=int(organization_id), execution_key=execution_key,
                    job_id=job_id, event_id=payload.get("event_id"),
                    workflow_id=payload.get("workflow_id"), stage="queue.completed",
                    status="completed" if completed else "lease_lost", worker_id=worker_id,
                    plan_hash=compiled.get("plan_hash"),
                    correlation_id=payload.get("correlation_id"), trace_id=payload.get("trace_id"),
                    evidence_key=f"{execution_key}:queue.completed",
                    receipt={"lease_completed": bool(completed)},
                )
            if completed and organization_id is not None and not self._uses_injected_queue:
                trace = golden_workflow_trace.assert_terminal_completed(
                    organization_id=int(organization_id),
                    job_id=job_id,
                    execution_key=execution_key,
                    plan_hash=compiled.get("plan_hash"),
                )
                result = {**result, "golden_trace": trace}
            return WorkerResult(status="completed" if completed else "lease_lost",
                                 job_id=job_id, executed=bool(result.get("executed")),
                                 detail=result).as_dict()
        if status in {"blocked", "idempotent_replay_blocked", "cancelled"}:
            reason = str(result.get("error") or status)
            if reason == "execution_authorization_used":
                failure = self.queue.fail(job_id, reason, worker_id=worker_id, retryable=False)
                final_status = status if failure.get("ok") else "lease_lost"
                queue_detail = failure
            else:
                cancelled = self.queue.cancel(job_id, worker_id=worker_id)
                final_status = status if cancelled else "lease_lost"
                queue_detail = {"ok": cancelled, "status": "cancelled" if cancelled else "lease_lost"}
            if organization_id is not None:
                self._terminal_evidence(
                    organization_id=int(organization_id), execution_key=execution_key,
                    job_id=job_id, payload=payload, worker_id=worker_id,
                    status=final_status, reason=reason,
                    plan_hash=compiled.get("plan_hash"),
                )
            return WorkerResult(status=final_status, job_id=job_id,
                                 executed=bool(result.get("executed")), detail={**result, "queue": queue_detail}).as_dict()
        failure = self.queue.fail(job_id, str(result.get("error") or status), worker_id=worker_id)
        if organization_id is not None:
            self._terminal_evidence(
                organization_id=int(organization_id), execution_key=execution_key,
                job_id=job_id, payload=payload, worker_id=worker_id,
                status="failed", reason=str(result.get("error") or status),
                plan_hash=compiled.get("plan_hash"),
            )
        return WorkerResult(status="failed", job_id=job_id, executed=bool(result.get("executed")),
                            detail={"runtime": result, "queue": failure}).as_dict()

    @staticmethod
    def _terminal_evidence(*, organization_id: int, execution_key: str,
                           job_id: int, payload: dict[str, Any], worker_id: str,
                           status: str, reason: str, plan_hash: str | None = None) -> None:
        execution_evidence.record(
            organization_id=organization_id, execution_key=execution_key, job_id=job_id,
            event_id=payload.get("event_id"), workflow_id=payload.get("workflow_id"),
            stage="worker.terminal", status=status, worker_id=worker_id,
            plan_hash=plan_hash, correlation_id=payload.get("correlation_id"),
            trace_id=payload.get("trace_id"),
            evidence_key=f"{execution_key}:terminal:{job_id}:{status}:{reason}",
            receipt={"reason": reason},
        )


def _validate_durable_identity(*, plan: dict[str, Any], payload: dict[str, Any],
                               claimed: dict[str, Any], organization_id: Any,
                               job_id: int) -> str | None:
    context = plan.get("context")
    if not isinstance(context, dict):
        return None
    checks = {
        "organization_id": (context.get("organization_id"), organization_id),
        "workflow_id": (context.get("workflow_id"), payload.get("workflow_id")),
        "execution_id": (context.get("execution_id"), payload.get("execution_id")),
        "job_id": (context.get("job_id"), job_id),
        "idempotency_key": (plan.get("idempotency_key"), payload.get("idempotency_key")),
        "execution_key": (plan.get("execution_key"), claimed.get("job_key")),
        "approval_id": (context.get("approval_id"), payload.get("approval_id")),
    }
    durable_identity = payload.get("execution_identity")
    if isinstance(durable_identity, dict):
        checks.update({
            "identity.organization_id": (durable_identity.get("organization_id"), organization_id),
            "identity.job_id": (durable_identity.get("job_id"), job_id),
            "identity.workflow_id": (durable_identity.get("workflow_id"), payload.get("workflow_id")),
            "identity.execution_id": (durable_identity.get("execution_id"), payload.get("execution_id")),
            "identity.idempotency_key": (durable_identity.get("idempotency_key"), payload.get("idempotency_key")),
            "identity.execution_key": (durable_identity.get("execution_key"), claimed.get("job_key")),
            "identity.approval_id": (durable_identity.get("approval_id"), payload.get("approval_id")),
        })
    for name, (expected, actual) in checks.items():
        if expected is None:
            continue
        if str(expected) != str(actual):
            return f"execution_identity_mismatch:{name}"
    return None


def _sync_automation_execution(*, execution_id: Any, workflow_id: Any,
                                organization_id: int, status: str,
                                result: dict[str, Any]) -> None:
    try:
        import json
        from datetime import datetime
        from app import db
        from app.models.automation import AutomationExecution, AutomationWorkflow
        execution = db.session.get(AutomationExecution, int(execution_id))
        if execution is None:
            return
        if workflow_id is not None and str(execution.workflow_id) != str(workflow_id):
            return
        workflow = db.session.get(AutomationWorkflow, execution.workflow_id)
        if workflow is None or int(workflow.organization_id) != int(organization_id):
            return
        execution.status = "completed" if status == "completed" else ("failed" if status == "failed" else str(status))
        execution.output_json = json.dumps(result, ensure_ascii=False, default=str)
        execution.completed_at = datetime.utcnow() if execution.status in {"completed", "failed"} else None
    except Exception:
        return


def _decision_hash(authorization: Any) -> str | None:
    if not isinstance(authorization, dict):
        return None
    direct = str(authorization.get("decision_hash") or "").strip()
    if direct:
        return direct
    handoff = authorization.get("gate_handoff")
    if isinstance(handoff, dict):
        value = str(handoff.get("decision_hash") or "").strip()
        return value or None
    return None


def _approval_hash(authorization: Any) -> str | None:
    if not isinstance(authorization, dict):
        return None
    token = str(authorization.get("token") or authorization.get("execution_token") or "")
    if not token:
        return None
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _datetime_from_epoch(value: float):
    from datetime import datetime
    return datetime.utcfromtimestamp(value)


def _numeric(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _timestamp(value: str) -> float:
    from datetime import datetime, timezone
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _legacy_plan_to_canonical(plan: Any, *, execution_key: str) -> dict[str, Any]:
    """Normalize legacy AutomationPlan/dict payloads into the canonical runtime contract."""
    if isinstance(plan, dict):
        canonical = dict(plan)
        canonical.setdefault("execution_key", execution_key)
        return canonical
    canonical = {
        "plan_id": str(getattr(plan, "plan_id", execution_key)),
        "organization_id": int(getattr(plan, "organization_id", 0) or 0),
        "trigger": str(getattr(plan, "trigger", "governed_worker")),
        "dry_run": bool(getattr(plan, "dry_run", False)),
        "approval_policy": str(getattr(plan, "approval_policy", "auto_safe")),
        "execution_key": execution_key,
        "parameters": {},
    }
    steps = getattr(plan, "steps", ()) or ()
    if steps:
        step = steps[0]
        canonical["action"] = str(getattr(step, "action", ""))
        canonical["parameters"] = dict(getattr(step, "parameters", {}) or {})
        canonical["risk"] = str(getattr(step, "risk", "low"))
        canonical["requires_approval"] = bool(getattr(step, "requires_approval", False))
    return canonical


governed_worker = GovernedWorker()

# Durable execution is tenant-scoped and fail-closed on ambiguous replay state.



