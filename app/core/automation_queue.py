from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from app import db
from app.models.automation_queue import AutomationQueueJob
from app.core.workflow_runtime import WorkflowIdentity, WorkflowState, unified_workflow_runtime
from app.core.workflow_coordinator import workflow_coordinator


class AutomationQueue:
    """Durable tenant queue with ownership, leases, retry caps, and deadlines."""

    VERSION = "2.0"
    DEFAULT_RETRY_DELAY = 30
    MAX_RETRY_DELAY = 3600

    def enqueue(self, envelope: dict[str, Any], *, delay_seconds: int = 0,
                deadline_seconds: int | None = None, commit: bool = True) -> dict[str, Any]:
        org_id = int(envelope["organization_id"])
        job_key = str(envelope["job_key"]).strip()
        if org_id <= 0 or not job_key:
            raise ValueError("queue_identity_required")
        existing = AutomationQueueJob.query.filter_by(
            organization_id=org_id, job_key=job_key
        ).first()
        if existing:
            return {"accepted": False, "status": "deduplicated", "job_id": existing.id}
        now = datetime.utcnow()
        deadline_at = None
        if deadline_seconds is not None:
            deadline_at = now + timedelta(seconds=max(1, int(deadline_seconds)))
        job = AutomationQueueJob(
            organization_id=org_id,
            job_key=job_key,
            event_id=envelope.get("event_id"),
            trigger_id=envelope.get("trigger_id"),
            workflow_id=envelope.get("workflow_id"),
            execution_id=envelope.get("execution_id"),
            idempotency_key=envelope.get("idempotency_key") or job_key,
            workflow_state=str(envelope.get("workflow_state") or WorkflowState.QUEUED),
            state_reason=str(envelope.get("workflow_state_reason") or "enqueued"),
            state_updated_at=now,
            payload_json=json.dumps(envelope, ensure_ascii=False, default=str),
            status="queued",
            priority=int(envelope.get("priority", 100)),
            available_at=now + timedelta(seconds=max(0, int(delay_seconds))),
            max_attempts=max(1, int(envelope.get("max_attempts", 3))),
            correlation_id=envelope.get("correlation_id"),
            trace_id=envelope.get("trace_id"),
            deadline_at=deadline_at,
        )
        db.session.add(job)
        try:
            db.session.flush()
            workflow_coordinator.record_initial_state(
                job.id, job.workflow_state, reason=job.state_reason,
                metadata={"organization_id": org_id, "execution_key": job.job_key},
            )
            if commit:
                db.session.commit()
        except Exception:
            db.session.rollback()
            existing = AutomationQueueJob.query.filter_by(
                organization_id=org_id, job_key=job_key
            ).first()
            if existing:
                return {"accepted": False, "status": "deduplicated", "job_id": existing.id}
            raise
        return {"accepted": True, "status": "queued", "job_id": job.id}
    def bind_execution_envelope(self, job_id: int, *, plan: dict[str, Any], authorization: dict[str, Any], commit: bool = True) -> dict[str, Any]:
        job = db.session.get(AutomationQueueJob, int(job_id))
        if not job:
            raise ValueError("workflow_job_not_found")
        if job.status not in {"queued", "leased"}:
            raise ValueError("execution_envelope_job_state_invalid")
        if job.workflow_state not in {WorkflowState.WAITING_APPROVAL, WorkflowState.QUEUED, WorkflowState.APPROVED, WorkflowState.PROCESSING}:
            raise ValueError("execution_envelope_workflow_state_invalid")
        if not isinstance(plan, dict) or not isinstance(authorization, dict):
            raise ValueError("execution_envelope_binding_required")
        payload = json.loads(job.payload_json or "{}")
        if not isinstance(payload, dict):
            raise ValueError("execution_envelope_payload_invalid")
        payload["execution_plan"] = dict(plan)
        payload["authorization"] = dict(authorization)
        payload["approval_id"] = payload.get("approval_id") or (plan.get("context") or {}).get("approval_id")
        payload["execution_identity"] = {
            "organization_id": job.organization_id,
            "job_id": job.id,
            "workflow_id": job.workflow_id,
            "execution_id": job.execution_id,
            "idempotency_key": job.idempotency_key,
            "execution_key": job.job_key,
            "plan_hash": authorization.get("plan_hash"),
            "decision_hash": (authorization.get("gate_handoff") or {}).get("decision_hash"),
            "approval_id": payload.get("approval_id"),
        }
        job.payload_json = json.dumps(payload, ensure_ascii=False, default=str)
        if commit:
            db.session.commit()
        return {"ok": True, "job_id": job.id, "plan_hash": authorization.get("plan_hash"), "execution_key": job.job_key}

    def transition_state(self, job_id: int, target: str, *, reason: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return workflow_coordinator.transition_job(
            job_id, target, reason=reason, actor="automation_queue", metadata=metadata
        )

    def claim(self, *, worker_id: str, lease_seconds: int = 60, organization_id: int | None = None, job_id: int | None = None) -> dict[str, Any] | None:
        worker_id = str(worker_id or "").strip()
        if not worker_id:
            raise ValueError("worker_id_required")
        now = datetime.utcnow()
        stale = AutomationQueueJob.query.filter(
            AutomationQueueJob.status == "leased",
            AutomationQueueJob.lease_until < now,
        ).all()
        for job in stale:
            from_state = job.workflow_state
            if unified_workflow_runtime.can_transition(from_state, WorkflowState.RETRYING) and unified_workflow_runtime.can_transition(WorkflowState.RETRYING, WorkflowState.QUEUED):
                workflow_coordinator.record_job_transition(
                    job.id, from_state, WorkflowState.RETRYING,
                    reason="lease_expired_recovered", actor="automation_queue",
                    metadata={"execution_key": job.job_key},
                )
                workflow_coordinator.record_job_transition(
                    job.id, WorkflowState.RETRYING, WorkflowState.QUEUED,
                    reason="lease_recovered", actor="automation_queue",
                    metadata={"execution_key": job.job_key},
                )
            job.status = "queued"
            job.lease_until = None
            job.lease_owner = None
        db.session.flush()

        filters = [AutomationQueueJob.status == "queued", AutomationQueueJob.workflow_state == WorkflowState.QUEUED, AutomationQueueJob.available_at <= now]
        if organization_id is not None:
            filters.append(AutomationQueueJob.organization_id == int(organization_id))
        if job_id is not None:
            filters.append(AutomationQueueJob.id == int(job_id))
        query = AutomationQueueJob.query.filter(*filters).order_by(
            AutomationQueueJob.priority.asc(), AutomationQueueJob.available_at.asc(),
            AutomationQueueJob.id.asc(),
        )
        if db.engine.dialect.name == "postgresql":
            job = query.with_for_update(skip_locked=True).first()
        else:
            job = query.first()
        if not job:
            db.session.commit()
            return None

        from_state = job.workflow_state
        if not unified_workflow_runtime.can_transition(job.workflow_state, WorkflowState.PROCESSING):
            db.session.rollback()
            raise ValueError(f"invalid_workflow_transition:{job.workflow_state}->{WorkflowState.PROCESSING}")
        workflow_coordinator.record_job_transition(
            job.id, from_state, WorkflowState.PROCESSING,
            reason="worker_claimed", actor="automation_queue",
            metadata={"worker_id": worker_id, "execution_key": job.job_key},
        )
        job.lease_until = now + timedelta(seconds=max(1, lease_seconds))
        job.lease_owner = worker_id
        job.attempts += 1
        db.session.commit()
        db.session.expire_all()
        claimed = db.session.get(AutomationQueueJob, job.id)
        if claimed is None:
            return None
        return {
            "job_id": claimed.id,
            "job_key": claimed.job_key,
            "organization_id": claimed.organization_id,
            "worker_id": worker_id,
            "attempt": claimed.attempts,
            "payload": json.loads(claimed.payload_json),
            "deadline_at": claimed.deadline_at.isoformat() if claimed.deadline_at else None,
        }
    @staticmethod
    def _owned(job: AutomationQueueJob, worker_id: str | None) -> bool:
        if not job.lease_owner:
            return worker_id is None
        return bool(worker_id) and job.lease_owner == str(worker_id)

    def complete(self, job_id: int, *, worker_id: str | None = None,
                 metadata: dict[str, Any] | None = None) -> bool:
        job = db.session.get(AutomationQueueJob, int(job_id))
        if not job or job.status != "leased" or not self._owned(job, worker_id):
            return False
        if not unified_workflow_runtime.can_transition(job.workflow_state, WorkflowState.COMPLETED):
            return False
        from_state = job.workflow_state
        workflow_coordinator.record_job_transition(
            job.id, from_state, WorkflowState.COMPLETED,
            reason="worker_completed", actor="automation_queue",
            metadata={"execution_key": job.job_key, **dict(metadata or {})},
        )
        db.session.commit()
        return True

    def fail(self, job_id: int, error: str, *, worker_id: str | None = None,
             retry_delay_seconds: int = DEFAULT_RETRY_DELAY, retryable: bool = True) -> dict[str, Any]:
        job = db.session.get(AutomationQueueJob, int(job_id))
        if not job:
            return {"ok": False, "status": "not_found"}
        if job.status == "leased" and not self._owned(job, worker_id):
            return {"ok": False, "status": "lease_owner_mismatch"}
        job.last_error = str(error)[:10000]
        from_state = job.workflow_state
        job.lease_until = None
        job.lease_owner = None
        if retryable and job.attempts < job.max_attempts:
            if not unified_workflow_runtime.can_transition(job.workflow_state, WorkflowState.RETRYING):
                return {"ok": False, "status": "invalid_workflow_transition"}
            if not unified_workflow_runtime.can_transition(WorkflowState.RETRYING, WorkflowState.QUEUED):
                return {"ok": False, "status": "invalid_workflow_transition"}
            delay = min(self.MAX_RETRY_DELAY, max(0, int(retry_delay_seconds)) * (2 ** max(0, job.attempts - 1)))
            workflow_coordinator.record_job_transition(
                job.id, from_state, WorkflowState.RETRYING,
                reason="execution_failed_retrying", actor="automation_queue",
                metadata={"error": str(error)[:500], "execution_key": job.job_key},
            )
            workflow_coordinator.record_job_transition(
                job.id, WorkflowState.RETRYING, WorkflowState.QUEUED,
                reason="retry_queued", actor="automation_queue",
                metadata={"execution_key": job.job_key},
            )
            job.available_at = datetime.utcnow() + timedelta(seconds=delay)
            job.status = "queued"
            status = "requeued"
        else:
            if not unified_workflow_runtime.can_transition(job.workflow_state, WorkflowState.FAILED):
                return {"ok": False, "status": "invalid_workflow_transition"}
            workflow_coordinator.record_job_transition(
                job.id, from_state, WorkflowState.FAILED,
                reason="retry_exhausted", actor="automation_queue",
                metadata={"error": str(error)[:500], "execution_key": job.job_key},
            )
            job.status = "dead_letter"
            status = "dead_letter"
        db.session.commit()
        return {"ok": True, "status": status, "attempts": job.attempts}
    def cancel(self, job_id: int, *, worker_id: str | None = None) -> bool:
        job = db.session.get(AutomationQueueJob, int(job_id))
        if not job or job.status in {"completed", "dead_letter", "cancelled"}:
            return False
        if job.status == "leased" and not self._owned(job, worker_id):
            return False
        if not unified_workflow_runtime.can_transition(job.workflow_state, WorkflowState.CANCELLED):
            return False
        from_state = job.workflow_state
        workflow_coordinator.record_job_transition(
            job.id, from_state, WorkflowState.CANCELLED,
            reason="cancelled", actor="automation_queue",
        )
        db.session.commit()
        return True

    def list_dead_letters(self, *, organization_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = AutomationQueueJob.query.filter(AutomationQueueJob.status == "dead_letter")
        if organization_id is not None:
            query = query.filter(AutomationQueueJob.organization_id == int(organization_id))
        jobs = query.order_by(AutomationQueueJob.created_at.desc()).limit(max(1, min(int(limit), 500))).all()
        return [self._summary(job) for job in jobs]

    def requeue_dead_letter(self, job_id: int, *, worker_id: str | None = None, replay_authorized: bool = False) -> dict[str, Any]:
        job = db.session.get(AutomationQueueJob, int(job_id))
        if job and job.workflow_state in {WorkflowState.COMPLETED, WorkflowState.CANCELLED, WorkflowState.EXPIRED, WorkflowState.REJECTED}:
            return {"ok": False, "status": "terminal_job_not_replayable"}
        if not job or job.status != "dead_letter":
            return {"ok": False, "status": "not_dead_letter"}
        if not worker_id:
            return {"ok": False, "status": "worker_id_required"}
        if job.workflow_state != WorkflowState.FAILED:
            if job.workflow_state == WorkflowState.QUEUED and job.status == "dead_letter":
                job.workflow_state = WorkflowState.FAILED
                job.state_version += 1
                job.state_reason = "legacy_dead_letter_normalized"
                job.state_updated_at = datetime.utcnow()
            else:
                return {"ok": False, "status": "invalid_workflow_transition"}
        if not unified_workflow_runtime.can_transition(job.workflow_state, WorkflowState.QUEUED):
            return {"ok": False, "status": "invalid_workflow_transition"}
        if not replay_authorized:
            return {"ok": False, "status": "replay_authorization_required"}
        workflow_coordinator.record_job_transition(
            job.id, WorkflowState.FAILED, WorkflowState.QUEUED,
            reason="dead_letter_requeued", actor="automation_queue",
            metadata={"execution_key": job.job_key, "replay_authorized": bool(replay_authorized)},
        )
        db.session.commit()
        return {"ok": True, "status": "requeued", "job_id": job.id}

    @staticmethod
    def _identity(*, claimed: AutomationQueueJob, payload: dict[str, Any]) -> WorkflowIdentity:
        return WorkflowIdentity(
            organization_id=int(claimed.organization_id),
            job_id=str(claimed.id),
            workflow_id=str(claimed.workflow_id or payload.get("workflow_id") or "unknown"),
            execution_id=str(claimed.execution_id or payload.get("execution_id") or claimed.job_key),
            idempotency_key=str(claimed.idempotency_key or payload.get("idempotency_key") or claimed.job_key),
        )

    @staticmethod
    def _summary(job: AutomationQueueJob) -> dict[str, Any]:
        return {"job_id": job.id, "job_key": job.job_key, "organization_id": job.organization_id,
                "workflow_id": job.workflow_id, "execution_id": job.execution_id,
                "workflow_state": job.workflow_state, "state_version": job.state_version,
                "event_id": job.event_id, "attempts": job.attempts,
                "max_attempts": job.max_attempts, "last_error": job.last_error,
                "created_at": job.created_at.isoformat(), "status": job.status}

    def recover_expired(self) -> int:
        now = datetime.utcnow()
        jobs = AutomationQueueJob.query.filter(
            AutomationQueueJob.status == "leased",
            AutomationQueueJob.lease_until < now,
        ).all()
        for job in jobs:
            from_state = job.workflow_state
            if unified_workflow_runtime.can_transition(from_state, WorkflowState.RETRYING) and unified_workflow_runtime.can_transition(WorkflowState.RETRYING, WorkflowState.QUEUED):
                workflow_coordinator.record_job_transition(
                    job.id, from_state, WorkflowState.RETRYING,
                    reason="lease_expired_recovered", actor="automation_queue",
                    metadata={"execution_key": job.job_key},
                )
                workflow_coordinator.record_job_transition(
                    job.id, WorkflowState.RETRYING, WorkflowState.QUEUED,
                    reason="lease_recovered", actor="automation_queue",
                    metadata={"execution_key": job.job_key},
                )
            job.status = "queued"
            job.lease_until = None
            job.lease_owner = None
        db.session.commit()
        return len(jobs)


automation_queue = AutomationQueue()
