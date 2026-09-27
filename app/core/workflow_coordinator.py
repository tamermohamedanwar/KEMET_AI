from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from app import db
from app.core.workflow_runtime import WorkflowIdentity, WorkflowState, WorkflowTransitionError, unified_workflow_runtime
from app.models.automation_queue import AutomationQueueJob
from app.models.workflow_transition import WorkflowTransitionRecord


class WorkflowCoordinator:
    VERSION = "1.2"

    def validate_context(self, *, job: AutomationQueueJob,
                         target: str, metadata: dict[str, Any] | None = None) -> None:
        payload = self._payload(job)
        metadata = dict(metadata or {})
        required = {
            "organization_id": int(job.organization_id),
            "workflow_id": str(job.workflow_id or payload.get("workflow_id") or ""),
            "execution_id": str(job.execution_id or payload.get("execution_id") or job.job_key),
            "idempotency_key": str(job.idempotency_key or payload.get("idempotency_key") or job.job_key),
        }
        for key, value in required.items():
            if not value:
                raise ValueError(f"workflow_identity_required:{key}")
        if metadata.get("organization_id") is not None and int(metadata["organization_id"]) != required["organization_id"]:
            raise ValueError("workflow_tenant_mismatch")
        if target == WorkflowState.WAITING_APPROVAL and not metadata.get("approval_id"):
            raise ValueError("workflow_approval_id_required")
        if target == WorkflowState.APPROVED:
            if not metadata.get("approval_id") or not metadata.get("plan_hash"):
                raise ValueError("workflow_approval_identity_required")
        if target == WorkflowState.PROCESSING:
            if job.workflow_state == WorkflowState.WAITING_APPROVAL:
                raise ValueError("workflow_approval_pending")
            if not metadata.get("execution_key"):
                raise ValueError("workflow_execution_key_required")
        if target in {WorkflowState.COMPLETED, WorkflowState.AMBIGUOUS}:
            if not metadata.get("execution_key"):
                raise ValueError("workflow_execution_key_required")

    def record_initial_state(self, job_id: int, target: str, *, reason: str,
                             metadata: dict[str, Any] | None = None) -> None:
        job = db.session.get(AutomationQueueJob, int(job_id))
        if not job:
            raise ValueError("workflow_job_not_found")
        payload = self._payload(job)
        identity = self._identity(job, payload)
        effective = dict(metadata or {})
        effective.setdefault("organization_id", identity.organization_id)
        effective.setdefault("execution_key", str(job.job_key))
        transition = unified_workflow_runtime.transition(
            identity, WorkflowState.CREATED, target, reason=reason, metadata=effective
        )
        self._record(transition, actor="workflow_coordinator")

    def transition_approval(self, job_id: int, target: str, *, approval_id: int,
                            reason: str, metadata: dict[str, Any] | None = None,
                            commit: bool = True) -> dict[str, Any]:
        data = dict(metadata or {})
        data["approval_id"] = int(approval_id)
        return self.transition_job(job_id, target, reason=reason, actor="approval_service", metadata=data, commit=commit)

    def transition_execution(self, job_id: int, target: str, *, execution_key: str,
                             reason: str, metadata: dict[str, Any] | None = None,
                             commit: bool = True) -> dict[str, Any]:
        data = dict(metadata or {})
        data["execution_key"] = str(execution_key)
        if target == WorkflowState.COMPLETED and not (data.get("evidence_id") or data.get("evidence_digest")):
            raise ValueError("workflow_evidence_required")
        return self.transition_job(job_id, target, reason=reason, actor="execution_runtime", metadata=data, commit=commit)

    def transition_job(
        self,
        job_id: int,
        target: str,
        *,
        reason: str,
        actor: str = "system",
        metadata: dict[str, Any] | None = None,
        commit: bool = True,
    ) -> dict[str, Any]:
        job = db.session.get(AutomationQueueJob, int(job_id))
        if not job:
            return {"ok": False, "status": "not_found"}
        payload = self._payload(job)
        identity = self._identity(job, payload)
        effective_metadata = dict(metadata or {})
        effective_metadata.setdefault("organization_id", identity.organization_id)
        effective_metadata.setdefault("execution_key", str(job.job_key))
        unified_workflow_runtime.assert_not_terminal(job.workflow_state)
        self.validate_context(job=job, target=target, metadata=effective_metadata)
        transition = unified_workflow_runtime.transition(
            identity,
            job.workflow_state,
            target,
            reason=reason,
            metadata=effective_metadata,
        )
        self._record(transition, actor=actor)
        self._apply_queue_state(job, target)
        job.state_version += 1
        job.state_reason = str(reason)[:500]
        job.state_updated_at = datetime.utcnow()
        if commit:
            db.session.commit()
        return {
            "ok": True,
            "status": "transitioned",
            "job_id": job.id,
            "workflow_state": target,
            "state_version": job.state_version,
        }

    def _record(self, transition, *, actor: str) -> None:
        metadata = dict(transition.metadata or {})
        raw = json.dumps(metadata, sort_keys=True, ensure_ascii=False, default=str)
        record = WorkflowTransitionRecord(
            organization_id=transition.identity.organization_id,
            job_id=transition.identity.job_id,
            workflow_id=transition.identity.workflow_id,
            execution_id=transition.identity.execution_id,
            idempotency_key=transition.identity.idempotency_key,
            from_state=transition.from_state,
            to_state=transition.to_state,
            reason=transition.reason,
            actor=str(actor)[:255],
            plan_hash=self._value(metadata, "plan_hash"),
            decision_hash=self._value(metadata, "decision_hash"),
            approval_id=self._value(metadata, "approval_id"),
            execution_key=self._value(metadata, "execution_key"),
            metadata_digest=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            metadata_json=raw,
        )
        db.session.add(record)

    @staticmethod
    def _payload(job: AutomationQueueJob) -> dict[str, Any]:
        try:
            value = json.loads(job.payload_json or "{}")
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _identity(job: AutomationQueueJob, payload: dict[str, Any]) -> WorkflowIdentity:
        return WorkflowIdentity(
            organization_id=int(job.organization_id),
            job_id=str(job.id),
            workflow_id=str(job.workflow_id or payload.get("workflow_id") or "unknown"),
            execution_id=str(job.execution_id or payload.get("execution_id") or job.job_key),
            idempotency_key=str(job.idempotency_key or payload.get("idempotency_key") or job.job_key),
        )

    @staticmethod
    def _value(metadata: dict[str, Any], key: str) -> str | None:
        value = metadata.get(key)
        return str(value) if value is not None else None

    @staticmethod
    def _apply_queue_state(job: AutomationQueueJob, target: str) -> None:
        now = datetime.utcnow()
        job.workflow_state = str(target)
        if target == WorkflowState.QUEUED:
            job.status = "queued"
            job.available_at = now
            job.lease_until = None
            job.lease_owner = None
        elif target == WorkflowState.PROCESSING:
            job.status = "leased"
        elif target == WorkflowState.CANCELLED:
            job.status = "cancelled"
            job.lease_until = None
            job.lease_owner = None
        elif target == WorkflowState.COMPLETED:
            job.status = "completed"
            job.completed_at = now
            job.lease_until = None
            job.lease_owner = None
        elif target == WorkflowState.FAILED:
            job.status = "dead_letter"
            job.lease_until = None
            job.lease_owner = None

    def record_job_transition(
        self,
        job_id: int,
        from_state: str,
        to_state: str,
        *,
        reason: str,
        actor: str = "system",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        job = db.session.get(AutomationQueueJob, int(job_id))
        if not job:
            raise ValueError("workflow_job_not_found")
        payload = self._payload(job)
        identity = self._identity(job, payload)
        effective_metadata = dict(metadata or {})
        effective_metadata.setdefault("organization_id", identity.organization_id)
        effective_metadata.setdefault("execution_key", str(job.job_key))
        current_state = str(job.workflow_state)
        from_state = str(from_state)
        to_state = str(to_state)
        if current_state != from_state:
            raise WorkflowTransitionError(
                f"workflow_persisted_state_mismatch:{current_state}!={from_state}"
            )
        self.validate_context(job=job, target=to_state, metadata=effective_metadata)
        transition = unified_workflow_runtime.transition(
            identity, from_state, to_state, reason=reason, metadata=effective_metadata
        )
        self._record(transition, actor=actor)
        self._apply_queue_state(job, to_state)
        job.state_version += 1
        job.state_reason = str(reason)[:500]
        job.state_updated_at = datetime.utcnow()

    def history(self, *, organization_id: int, job_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = (WorkflowTransitionRecord.query
                .filter_by(organization_id=int(organization_id), job_id=str(job_id))
                .order_by(WorkflowTransitionRecord.id.asc())
                .limit(max(1, min(int(limit), 500))).all())
        return [self._as_dict(row) for row in rows]

    @staticmethod
    def _as_dict(row: WorkflowTransitionRecord) -> dict[str, Any]:
        return {
            "id": row.id,
            "organization_id": row.organization_id,
            "job_id": row.job_id,
            "workflow_id": row.workflow_id,
            "execution_id": row.execution_id,
            "idempotency_key": row.idempotency_key,
            "from_state": row.from_state,
            "to_state": row.to_state,
            "reason": row.reason,
            "actor": row.actor,
            "plan_hash": row.plan_hash,
            "decision_hash": row.decision_hash,
            "approval_id": row.approval_id,
            "execution_key": row.execution_key,
            "metadata_digest": row.metadata_digest,
            "created_at": row.created_at.isoformat(),
        }


workflow_coordinator = WorkflowCoordinator()
