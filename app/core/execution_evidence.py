from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app import db
from app.models.execution_evidence import ExecutionEvidence


class ExecutionEvidenceService:
    VERSION = "1.0"

    def record(self, *, organization_id: int, execution_key: str, stage: str,
               status: str, evidence_key: str, job_id: int | None = None,
               event_id: str | None = None, workflow_id: str | None = None,
               worker_id: str | None = None, plan_hash: str | None = None,
               correlation_id: str | None = None, trace_id: str | None = None,
               receipt: dict[str, Any] | None = None) -> dict[str, Any]:
        existing = ExecutionEvidence.query.filter_by(
            organization_id=int(organization_id), evidence_key=str(evidence_key)
        ).first()
        if existing:
            return self._as_dict(existing)
        row = ExecutionEvidence(
            organization_id=int(organization_id), execution_key=str(execution_key),
            job_id=job_id, event_id=event_id, workflow_id=workflow_id,
            stage=str(stage), status=str(status), worker_id=worker_id,
            plan_hash=plan_hash, correlation_id=correlation_id, trace_id=trace_id,
            evidence_key=str(evidence_key),
            receipt_json=json.dumps(receipt or {}, ensure_ascii=False, default=str),
            created_at=datetime.utcnow(),
        )
        db.session.add(row)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            existing = ExecutionEvidence.query.filter_by(
                organization_id=int(organization_id), evidence_key=str(evidence_key)
            ).first()
            if existing:
                return self._as_dict(existing)
            raise
        return self._as_dict(row)

    def history(self, *, organization_id: int, execution_key: str,
                limit: int = 100) -> list[dict[str, Any]]:
        rows = ExecutionEvidence.query.filter_by(
            organization_id=int(organization_id), execution_key=str(execution_key)
        ).order_by(ExecutionEvidence.created_at.asc(), ExecutionEvidence.id.asc()).limit(
            max(1, min(int(limit), 500))
        ).all()
        return [self._as_dict(row) for row in rows]

    @staticmethod
    def _as_dict(row: ExecutionEvidence) -> dict[str, Any]:
        return {
            "id": row.id, "organization_id": row.organization_id,
            "execution_key": row.execution_key, "job_id": row.job_id,
            "event_id": row.event_id, "workflow_id": row.workflow_id,
            "stage": row.stage, "status": row.status, "worker_id": row.worker_id,
            "plan_hash": row.plan_hash, "correlation_id": row.correlation_id,
            "trace_id": row.trace_id, "evidence_key": row.evidence_key,
            "receipt": json.loads(row.receipt_json or "{}"),
            "created_at": row.created_at.isoformat(),
        }


execution_evidence = ExecutionEvidenceService()
