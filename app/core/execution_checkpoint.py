from __future__ import annotations

import json
from typing import Any

from flask import has_app_context

from app import db
from app.models.automation_execution_checkpoint import AutomationExecutionCheckpoint


class ExecutionCheckpointService:
    VERSION = "1.0"

    def begin_step(
        self, *, organization_id: int, execution_key: str, plan_hash: str,
        step_id: str, ordinal: int, worker_id: str | None = None,
    ) -> dict[str, Any]:
        self._require_context()
        row = AutomationExecutionCheckpoint.query.filter_by(
            organization_id=int(organization_id), execution_key=str(execution_key), step_id=str(step_id)
        ).first()
        if row:
            if row.plan_hash != str(plan_hash):
                return {"status": "plan_hash_mismatch", "checkpoint": self._as_dict(row)}
            if row.status == "completed":
                return {"status": "completed", "checkpoint": self._as_dict(row)}
            if row.status in {"started", "ambiguous"}:
                return {"status": "ambiguous", "checkpoint": self._as_dict(row)}
            row.status = "started"
            row.attempt += 1
            row.worker_id = worker_id
            db.session.commit()
            return {"status": "started", "checkpoint": self._as_dict(row)}
        row = AutomationExecutionCheckpoint(
            organization_id=int(organization_id), execution_key=str(execution_key),
            plan_hash=str(plan_hash), step_id=str(step_id), ordinal=int(ordinal),
            status="started", attempt=1, worker_id=worker_id,
            result_json=json.dumps({}, ensure_ascii=False),
        )
        db.session.add(row)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            existing = AutomationExecutionCheckpoint.query.filter_by(
                organization_id=int(organization_id), execution_key=str(execution_key), step_id=str(step_id)
            ).first()
            if existing:
                return {"status": "ambiguous", "checkpoint": self._as_dict(existing)}
            raise
        return {"status": "started", "checkpoint": self._as_dict(row)}

    def complete_step(self, *, organization_id: int, execution_key: str,
                      plan_hash: str, step_id: str, result: dict[str, Any],
                      worker_id: str | None = None) -> dict[str, Any]:
        self._require_context()
        row = AutomationExecutionCheckpoint.query.filter_by(
            organization_id=int(organization_id), execution_key=str(execution_key), step_id=str(step_id)
        ).first()
        if not row:
            return {"status": "missing"}
        if row.plan_hash != str(plan_hash):
            return {"status": "plan_hash_mismatch", "checkpoint": self._as_dict(row)}
        if row.status == "completed":
            return {"status": "completed", "checkpoint": self._as_dict(row)}
        if row.status != "started":
            return {"status": "invalid_state", "checkpoint": self._as_dict(row)}
        if row.worker_id and worker_id and row.worker_id != worker_id:
            return {"status": "worker_mismatch", "checkpoint": self._as_dict(row)}
        row.status = "completed"
        row.result_json = json.dumps(result or {}, ensure_ascii=False, default=str)
        db.session.commit()
        return {"status": "completed", "checkpoint": self._as_dict(row)}

    def mark_ambiguous(self, *, organization_id: int, execution_key: str,
                       plan_hash: str, step_id: str, reason: str,
                       worker_id: str | None = None) -> dict[str, Any]:
        self._require_context()
        row = AutomationExecutionCheckpoint.query.filter_by(
            organization_id=int(organization_id), execution_key=str(execution_key), step_id=str(step_id)
        ).first()
        if not row:
            return {"status": "missing"}
        if row.plan_hash != str(plan_hash):
            return {"status": "plan_hash_mismatch", "checkpoint": self._as_dict(row)}
        if row.worker_id and worker_id and row.worker_id != worker_id:
            return {"status": "worker_mismatch", "checkpoint": self._as_dict(row)}
        row.status = "ambiguous"
        row.result_json = json.dumps({"error": reason}, ensure_ascii=False)
        db.session.commit()
        return {"status": "ambiguous", "checkpoint": self._as_dict(row)}

    def history(self, *, organization_id: int, execution_key: str) -> list[dict[str, Any]]:
        self._require_context()
        rows = AutomationExecutionCheckpoint.query.filter_by(
            organization_id=int(organization_id), execution_key=str(execution_key)
        ).order_by(AutomationExecutionCheckpoint.ordinal.asc()).all()
        return [self._as_dict(row) for row in rows]

    @staticmethod
    def _as_dict(row: AutomationExecutionCheckpoint) -> dict[str, Any]:
        return {
            "id": row.id, "organization_id": row.organization_id,
            "execution_key": row.execution_key, "plan_hash": row.plan_hash,
            "step_id": row.step_id, "ordinal": row.ordinal, "status": row.status,
            "attempt": row.attempt, "worker_id": row.worker_id,
            "result": json.loads(row.result_json or "{}"),
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }

    @staticmethod
    def _require_context() -> None:
        if not has_app_context():
            raise RuntimeError("execution_checkpoint_requires_app_context")


execution_checkpoint = ExecutionCheckpointService()
