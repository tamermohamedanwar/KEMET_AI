from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Callable

from app.core.automation_control_plane import automation_control_plane
from app.core.automation_queue import AutomationQueue, automation_queue
from app.core.automation_runtime import AutomationRuntime, automation_runtime
from app.core.execution_ledger import ExecutionLedger, execution_ledger
from app.core.execution_telemetry import execution_telemetry
from app.core.automation_outcome_service import automation_outcome_service
from app.core.execution_evidence import execution_evidence
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
        self.ledger = ledger or execution_ledger

    def process_one(self, *, worker_id: str,
                    plan_resolver: Callable[[dict[str, Any]], Any],
                    lease_seconds: int = 60,
                    org_limit: int = WorkerCoordinator.DEFAULT_ORG_LIMIT,
                    global_limit: int = WorkerCoordinator.DEFAULT_GLOBAL_LIMIT) -> dict[str, Any]:
        claimed = self.queue.claim(worker_id=worker_id, lease_seconds=lease_seconds)
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
        if self.coordinator.is_cancelled(job_id=job_id, worker_id=worker_id):
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
        if self.coordinator.is_cancelled(job_id=job_id, worker_id=worker_id):
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
            approval_hash = _approval_hash(payload.get("authorization"))
            started = self.ledger.begin(
                organization_id=int(organization_id), execution_key=execution_key,
                plan_hash=str(compiled["plan_hash"]), job_id=job_id, worker_id=worker_id,
                approval_hash=approval_hash, trace_id=payload.get("trace_id"),
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
                receipt={"ledger_id": ledger_record.get("id") if ledger_record else None},
            )
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
                result = self.runtime.execute(
                    plan, authorization=payload.get("authorization"),
                    actor_id=str(payload.get("actor_id") or worker_id),
                    execution_key=execution_key,
                    deadline_at=_timestamp(deadline_at) if deadline_at else None,
                )
            except Exception:
                execution_telemetry.event("execution.failed", attributes={"kemet.error_type": "runtime_exception"})
                if organization_id is not None:
                    automation_outcome_service.record(
                        organization_id=int(organization_id), status="failed", executed=False,
                        job_id=job_id, workflow_id=payload.get("workflow_id"), event_id=payload.get("event_id"),
                        retry_count=max(0, int(claimed.get("attempt", 1)) - 1),
                        correlation_id=payload.get("correlation_id"), trace_id=payload.get("trace_id"),
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
            status = str(result.get("status") or "execution_failed")
            execution_telemetry.event(
                "execution.completed" if status == "completed" else "execution.finished",
                attributes={"kemet.status": status, "kemet.executed": bool(result.get("executed"))},
            )

        if organization_id is not None:
            outcome = automation_outcome_service.record(
                organization_id=int(organization_id), status=status, executed=bool(result.get("executed")),
                job_id=job_id, workflow_id=payload.get("workflow_id"), event_id=payload.get("event_id"),
                retry_count=max(0, int(claimed.get("attempt", 1)) - 1),
                correlation_id=payload.get("correlation_id"), trace_id=payload.get("trace_id"),
                business_outcome=result.get("business_outcome"), receipt=result.get("receipt") or result,
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
            execution_evidence.record(
                organization_id=int(organization_id), execution_key=execution_key,
                job_id=job_id, event_id=payload.get("event_id"),
                workflow_id=payload.get("workflow_id"), stage="runtime.finished",
                status=status, worker_id=worker_id,
                plan_hash=compiled.get("plan_hash"),
                correlation_id=payload.get("correlation_id"), trace_id=payload.get("trace_id"),
                evidence_key=f"{execution_key}:runtime.finished",
                receipt=receipt,
            )
        if status == "completed":
            completed = self.queue.complete(job_id, worker_id=worker_id)
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
            return WorkerResult(status="completed" if completed else "lease_lost",
                                 job_id=job_id, executed=bool(result.get("executed")),
                                 detail=result).as_dict()
        if status in {"blocked", "idempotent_replay_blocked", "cancelled"}:
            cancelled = self.queue.cancel(job_id, worker_id=worker_id)
            final_status = status if cancelled else "lease_lost"
            if organization_id is not None:
                self._terminal_evidence(
                    organization_id=int(organization_id), execution_key=execution_key,
                    job_id=job_id, payload=payload, worker_id=worker_id,
                    status=final_status, reason=str(result.get("error") or status),
                    plan_hash=compiled.get("plan_hash"),
                )
            return WorkerResult(status=final_status, job_id=job_id,
                                 executed=bool(result.get("executed")), detail=result).as_dict()
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


def _approval_hash(authorization: Any) -> str | None:
    if not isinstance(authorization, dict):
        return None
    token = str(authorization.get("token") or authorization.get("execution_token") or "")
    if not token:
        return None
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _timestamp(value: str) -> float:
    from datetime import datetime, timezone
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


governed_worker = GovernedWorker()

# Durable execution is tenant-scoped and fail-closed on ambiguous replay state.



