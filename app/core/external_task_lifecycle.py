from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Mapping

from app import db
from app.core.execution_ledger import execution_ledger
from app.core.execution_evidence import execution_evidence
from app.models.external_task import ExternalTaskRecord


class ExternalTaskLifecycleError(ValueError):
    pass


class ExternalTaskLifecycle:
    VERSION = "1.1"
    TERMINAL = frozenset({"completed", "failed", "cancelled"})
    VALID = frozenset({"submitting", "submitted", "running", "completed", "failed", "cancelled", "ambiguous"})
    TRANSITIONS = {
        "submitting": frozenset({"submitted", "ambiguous"}),
        "submitted": frozenset({"submitted", "running", "failed", "ambiguous"}),
        "running": frozenset({"running", "completed", "failed", "cancelled", "ambiguous"}),
        "completed": frozenset({"completed"}),
        "failed": frozenset({"failed"}),
        "cancelled": frozenset({"cancelled"}),
        "ambiguous": frozenset({"ambiguous"}),
    }

    @staticmethod
    def _safe_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
        blocked = {"api_key", "authorization", "token", "secret", "password", "credential", "cookie"}

        def clean(value: Any) -> Any:
            if isinstance(value, Mapping):
                return {
                    str(key): clean(item) for key, item in value.items()
                    if str(key).lower() not in blocked
                }
            if isinstance(value, (list, tuple)):
                return [clean(item) for item in value]
            if isinstance(value, (str, int, float, bool)) or value is None:
                return value
            return str(value)

        return clean(dict(metadata or {}))

    def begin_submission(
        self, *, organization_id: int, provider_id: str, execution_key: str,
        plan_hash: str, action: str, request_id: str | None = None,
        job_id: int | None = None, trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        existing = ExternalTaskRecord.query.filter_by(
            organization_id=int(organization_id), execution_key=str(execution_key), action=str(action)
        ).first()
        if existing:
            if existing.plan_hash != str(plan_hash) or existing.provider_id != str(provider_id):
                raise ExternalTaskLifecycleError("external_task_execution_identity_mismatch")
            if existing.status == "submitting" and existing.external_task_id.startswith("pending:"):
                raise ExternalTaskLifecycleError("external_task_submission_in_progress")
            return {"created": False, "record": self._as_dict(existing)}
        row = ExternalTaskRecord(
            organization_id=int(organization_id), provider_id=str(provider_id),
            external_task_id=f"pending:{hashlib.sha256(str(execution_key).encode()).hexdigest()}",
            execution_key=str(execution_key), plan_hash=str(plan_hash),
            action=str(action), status="submitting", request_id=str(request_id) if request_id else None,
            metadata_json=json.dumps({}, ensure_ascii=False), created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(), last_seen_at=datetime.utcnow(),
        )
        db.session.add(row)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            existing = ExternalTaskRecord.query.filter_by(
                organization_id=int(organization_id), execution_key=str(execution_key), action=str(action)
            ).first()
            if existing:
                raise ExternalTaskLifecycleError("external_task_submission_in_progress")
            raise
        execution_evidence.record(
            organization_id=organization_id, execution_key=execution_key,
            stage="external_task.submission_started", status="submitting",
            evidence_key=f"{execution_key}:external_task.submission_started",
            job_id=job_id, plan_hash=plan_hash, trace_id=trace_id, correlation_id=correlation_id,
            receipt={"provider_id": provider_id, "action": action},
        )
        return {"created": True, "record": self._as_dict(row)}

    def create_submission(
        self, *, organization_id: int, provider_id: str, external_task_id: str,
        execution_key: str, plan_hash: str, action: str, request_id: str | None = None,
        metadata: Mapping[str, Any] | None = None, job_id: int | None = None,
        trace_id: str | None = None, correlation_id: str | None = None,
    ) -> dict[str, Any]:
        if not external_task_id or not execution_key or not plan_hash or not action:
            raise ExternalTaskLifecycleError("external_task_identity_required")
        existing = ExternalTaskRecord.query.filter_by(
            organization_id=int(organization_id), execution_key=str(execution_key), action=str(action)
        ).first()
        if existing:
            if existing.plan_hash != str(plan_hash) or existing.provider_id != str(provider_id):
                raise ExternalTaskLifecycleError("external_task_identity_conflict")
            if existing.external_task_id != str(external_task_id):
                if existing.status == "submitting" and existing.external_task_id.startswith("pending:"):
                    existing.external_task_id = str(external_task_id)
                    existing.status = "submitted"
                    existing.request_id = str(request_id) if request_id else existing.request_id
                    existing.updated_at = datetime.utcnow()
                    existing.last_seen_at = datetime.utcnow()
                    db.session.commit()
                else:
                    raise ExternalTaskLifecycleError("external_task_identity_conflict")
            return self._as_dict(existing)
        existing_provider = ExternalTaskRecord.query.filter_by(
            provider_id=str(provider_id), external_task_id=str(external_task_id)
        ).first()
        if existing_provider:
            if existing_provider.organization_id != int(organization_id):
                raise ExternalTaskLifecycleError("external_task_cross_tenant_conflict")
            return self._as_dict(existing_provider)
        row = ExternalTaskRecord(
            organization_id=int(organization_id), provider_id=str(provider_id),
            external_task_id=str(external_task_id), execution_key=str(execution_key),
            plan_hash=str(plan_hash), action=str(action), status="submitted",
            request_id=str(request_id) if request_id else None,
            metadata_json=json.dumps(self._safe_metadata(metadata), ensure_ascii=False),
            created_at=datetime.utcnow(), updated_at=datetime.utcnow(), last_seen_at=datetime.utcnow(),
        )
        db.session.add(row)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            existing = ExternalTaskRecord.query.filter_by(
                organization_id=int(organization_id), execution_key=str(execution_key), action=str(action)
            ).first()
            if existing:
                return self._as_dict(existing)
            raise
        execution_evidence.record(
            organization_id=organization_id, execution_key=execution_key,
            stage="external_task.submitted", status="submitted",
            evidence_key=f"{execution_key}:external_task.submitted",
            job_id=job_id, plan_hash=plan_hash, trace_id=trace_id,
            correlation_id=correlation_id,
            receipt={"provider_id": provider_id, "external_task_id": external_task_id, "request_id": request_id},
        )
        return self._as_dict(row)

    def update_state(
        self, *, organization_id: int, execution_key: str, status: str,
        provider_id: str | None = None, external_task_id: str | None = None,
        plan_hash: str | None = None, metadata: Mapping[str, Any] | None = None,
        job_id: int | None = None, trace_id: str | None = None,
        correlation_id: str | None = None,
    ) -> dict[str, Any]:
        if status not in self.VALID:
            raise ExternalTaskLifecycleError("invalid_external_task_status")
        row = ExternalTaskRecord.query.filter_by(
            organization_id=int(organization_id), execution_key=str(execution_key)
        ).first()
        if not row:
            raise ExternalTaskLifecycleError("external_task_not_found")
        if provider_id and row.provider_id != str(provider_id):
            raise ExternalTaskLifecycleError("provider_mismatch")
        if external_task_id and row.external_task_id != str(external_task_id):
            raise ExternalTaskLifecycleError("external_task_id_mismatch")
        if plan_hash and row.plan_hash != str(plan_hash):
            raise ExternalTaskLifecycleError("plan_hash_mismatch")
        if status not in self.TRANSITIONS[row.status]:
            raise ExternalTaskLifecycleError(f"invalid_transition:{row.status}->{status}")
        row.status = str(status)
        row.last_seen_at = datetime.utcnow()
        if metadata:
            current = json.loads(row.metadata_json or "{}")
            current.update(self._safe_metadata(metadata))
            row.metadata_json = json.dumps(current, ensure_ascii=False)
        row.updated_at = datetime.utcnow()
        db.session.commit()
        execution_evidence.record(
            organization_id=organization_id, execution_key=execution_key,
            stage="external_task.state_changed", status=status,
            evidence_key=f"{execution_key}:external_task.state_changed:{status}",
            job_id=job_id, plan_hash=row.plan_hash, trace_id=trace_id,
            correlation_id=correlation_id,
            receipt={"provider_id": row.provider_id, "external_task_id": row.external_task_id, "status": status},
        )
        return self._as_dict(row)

    def mark_ambiguous(self, *, organization_id: int, execution_key: str,
                       reason: str | None = None, job_id: int | None = None,
                       trace_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
        row = self.update_state(
            organization_id=organization_id, execution_key=execution_key,
            status="ambiguous", job_id=job_id, trace_id=trace_id,
            correlation_id=correlation_id, metadata={"ambiguity_reason": reason or "unknown"},
        )
        execution_evidence.record(
            organization_id=organization_id, execution_key=execution_key,
            stage="external_task.ambiguous", status="ambiguous",
            evidence_key=f"{execution_key}:external_task.ambiguous",
            job_id=job_id, plan_hash=row["plan_hash"], trace_id=trace_id,
            correlation_id=correlation_id,
            receipt={"provider_id": row["provider_id"], "external_task_id": row["external_task_id"]},
        )
        return row

    def reconcile_provider_completion(
        self, *, organization_id: int, execution_key: str, provider_id: str,
        external_task_id: str, plan_hash: str, request_id: str | None = None,
        result: Any = None, error: Any = None, metadata: Mapping[str, Any] | None = None,
        trace_id: str | None = None, correlation_id: str | None = None,
    ) -> dict[str, Any]:
        """Accept a late provider completion only for the exact reserved task identity."""
        row = ExternalTaskRecord.query.filter_by(
            organization_id=int(organization_id), execution_key=str(execution_key)
        ).first()
        if not row:
            raise ExternalTaskLifecycleError("external_task_not_found")
        if row.provider_id != str(provider_id):
            raise ExternalTaskLifecycleError("provider_mismatch")
        if row.external_task_id != str(external_task_id):
            raise ExternalTaskLifecycleError("external_task_id_mismatch")
        if row.plan_hash != str(plan_hash):
            raise ExternalTaskLifecycleError("plan_hash_mismatch")
        if request_id and row.request_id and row.request_id != str(request_id):
            raise ExternalTaskLifecycleError("provider_request_id_mismatch")
        if row.status == "completed":
            current = self._as_dict(row)
            current_metadata = current.get("metadata") or {}
            if result is not None and current_metadata.get("result") != result:
                raise ExternalTaskLifecycleError("completed_result_substitution")
            return current
        if row.status in {"failed", "cancelled"}:
            raise ExternalTaskLifecycleError("stale_external_task_reconciliation")
        if row.status not in {"submitted", "running", "ambiguous"}:
            raise ExternalTaskLifecycleError("stale_external_task_reconciliation")

        current = json.loads(row.metadata_json or "{}")
        incoming = self._safe_metadata(metadata)
        if result is not None:
            incoming["result"] = result
        if error is not None:
            incoming["error"] = error
        incoming["reconciled"] = True
        incoming["reconciliation_identity"] = {
            "organization_id": int(organization_id), "execution_key": str(execution_key),
            "provider_id": str(provider_id), "external_task_id": str(external_task_id),
            "request_id": row.request_id or (str(request_id) if request_id else None),
            "plan_hash": str(plan_hash),
        }
        current.update(incoming)
        final_status = "completed" if error is None else "failed"
        result_digest = None
        if result is not None:
            result_digest = hashlib.sha256(
                json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
            ).hexdigest()
        try:
            execution_ledger.reconcile_completion(
                organization_id=int(organization_id), execution_key=str(execution_key),
                provider_id=str(provider_id), external_task_id=str(external_task_id),
                request_id=str(request_id) if request_id else row.request_id,
                status=final_status, result_digest=result_digest,
            )
        except ValueError as exc:
            raise ExternalTaskLifecycleError(str(exc)) from exc
        row.status = final_status
        if request_id and not row.request_id:
            row.request_id = str(request_id)
        row.metadata_json = json.dumps(current, ensure_ascii=False)
        row.last_seen_at = datetime.utcnow()
        row.updated_at = datetime.utcnow()
        db.session.commit()
        execution_evidence.record(
            organization_id=organization_id, execution_key=execution_key,
            stage="external_task.provider_reconciled", status=row.status,
            evidence_key=f"{execution_key}:external_task.provider_reconciled:{row.status}",
            plan_hash=row.plan_hash, trace_id=trace_id, correlation_id=correlation_id,
            receipt={
                "provider_id": row.provider_id, "external_task_id": row.external_task_id,
                "request_id": row.request_id, "status": row.status,
            },
        )
        return self._as_dict(row)

    def get(self, *, organization_id: int, execution_key: str) -> dict[str, Any] | None:
        row = ExternalTaskRecord.query.filter_by(
            organization_id=int(organization_id), execution_key=str(execution_key)
        ).first()
        return self._as_dict(row) if row else None

    @staticmethod
    def _as_dict(row: ExternalTaskRecord) -> dict[str, Any]:
        return {
            "id": row.id, "organization_id": row.organization_id, "provider_id": row.provider_id,
            "external_task_id": row.external_task_id, "execution_key": row.execution_key,
            "plan_hash": row.plan_hash, "action": row.action, "status": row.status,
            "request_id": row.request_id, "metadata": json.loads(row.metadata_json or "{}"),
            "created_at": row.created_at.isoformat(), "updated_at": row.updated_at.isoformat(),
            "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        }


external_task_lifecycle = ExternalTaskLifecycle()
