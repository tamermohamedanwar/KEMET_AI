from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app import db
from app.models.automation_execution_ledger import AutomationExecutionLedger


ExecutionLedgerRecord = AutomationExecutionLedger


class ExecutionLedger:
    """Durable execution identity and replay ledger."""

    VERSION = "1.0"

    def get(self, *, organization_id: int, execution_key: str) -> dict[str, Any] | None:
        row = ExecutionLedgerRecord.query.filter_by(
            organization_id=int(organization_id), execution_key=str(execution_key)
        ).first()
        if not row:
            return None
        return self._as_dict(row)

    def begin(self, *, organization_id: int, execution_key: str,
              plan_hash: str, job_id: int | None = None,
              worker_id: str | None = None, approval_hash: str | None = None,
              trace_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
        existing = self.get(organization_id=organization_id, execution_key=execution_key)
        if existing:
            return {"created": False, "status": existing["status"], "record": existing}
        row = ExecutionLedgerRecord(
            organization_id=int(organization_id), execution_key=str(execution_key),
            plan_hash=str(plan_hash), job_id=job_id, worker_id=worker_id,
            status="started", approval_hash=approval_hash, trace_id=trace_id,
            correlation_id=correlation_id, receipt_json=json.dumps({}, ensure_ascii=False),
            created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        )
        db.session.add(row)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            existing = self.get(organization_id=organization_id, execution_key=execution_key)
            if existing:
                return {"created": False, "status": existing["status"], "record": existing}
            raise
        return {"created": True, "status": "started", "record": self._as_dict(row)}

    def finish(self, *, organization_id: int, execution_key: str,
               status: str, receipt: dict[str, Any] | None = None) -> bool:
        row = ExecutionLedgerRecord.query.filter_by(
            organization_id=int(organization_id), execution_key=str(execution_key)
        ).first()
        if not row:
            return False
        row.status = str(status)
        row.receipt_json = json.dumps(receipt or {}, ensure_ascii=False, default=str)
        row.updated_at = datetime.utcnow()
        db.session.commit()
        return True

    @staticmethod
    def _as_dict(row: ExecutionLedgerRecord) -> dict[str, Any]:
        return {
            "id": row.id, "organization_id": row.organization_id,
            "execution_key": row.execution_key, "plan_hash": row.plan_hash,
            "job_id": row.job_id, "worker_id": row.worker_id, "status": row.status,
            "approval_hash": row.approval_hash, "trace_id": row.trace_id,
            "correlation_id": row.correlation_id,
            "receipt": json.loads(row.receipt_json or "{}"),
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }


execution_ledger = ExecutionLedger()


def ledger_status(*, organization_id: int, execution_key: str) -> dict[str, Any] | None:
    return execution_ledger.get(
        organization_id=organization_id, execution_key=execution_key,
    )


# Durable ledger is intentionally separate from runtime memory so worker restarts preserve identity.


# The ledger is tenant-scoped by design; execution keys are never global across organizations.


# Future runtime integration will bind approval_hash and plan_hash before execution begins.


# This keeps the core provider-neutral and independent of any external workflow engine.


# End of durable execution ledger module.


# Versioned for incremental runtime integration.


# No autonomous external side effects are performed by this ledger.


# Ledger state is evidence for governance and observability, not an authorization bypass.


# Ready for governed runtime integration.


# Maintains strict separation between planning, authorization, execution, and evidence.


# End.


# Final marker.


# Durable execution identity remains tenant-scoped and replay-safe.


# End of module.
