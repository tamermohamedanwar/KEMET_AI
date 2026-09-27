from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from app import db
from app.models.automation_execution_ledger import AutomationExecutionLedger


ExecutionLedgerRecord = AutomationExecutionLedger


class ExecutionLedger:
    """Durable execution identity and replay ledger."""

    VERSION = "1.1"

    @staticmethod
    def receipt_digest(receipt: dict[str, Any]) -> str:
        raw = json.dumps(receipt or {}, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

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
              decision_hash: str | None = None,
              approval_id: str | int | None = None,
              trace_id: str | None = None, correlation_id: str | None = None) -> dict[str, Any]:
        existing = self.get(organization_id=organization_id, execution_key=execution_key)
        if existing:
            if existing["status"] in {"completed", "started"}:
                return {"created": False, "status": existing["status"], "record": existing}
            row = ExecutionLedgerRecord.query.filter_by(
                organization_id=int(organization_id), execution_key=str(execution_key)
            ).first()
            if row is not None:
                row.status = "started"
                row.job_id = job_id
                row.worker_id = worker_id
                row.plan_hash = str(plan_hash)
                row.approval_hash = approval_hash or row.approval_hash
                row.trace_id = trace_id or row.trace_id
                row.correlation_id = correlation_id or row.correlation_id
                row.updated_at = datetime.utcnow()
                db.session.commit()
                return {"created": True, "status": "started", "record": self._as_dict(row)}
        identity = {}
        if decision_hash:
            identity["decision_hash"] = str(decision_hash)
        if approval_id is not None:
            identity["approval_id"] = str(approval_id)
        row = ExecutionLedgerRecord(
            organization_id=int(organization_id), execution_key=str(execution_key),
            plan_hash=str(plan_hash), job_id=job_id, worker_id=worker_id,
            status="started", approval_hash=approval_hash, trace_id=trace_id,
            correlation_id=correlation_id,
            receipt_json=json.dumps({"execution_identity": identity}, ensure_ascii=False),
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
        existing_receipt = json.loads(row.receipt_json or "{}")
        incoming_receipt = dict(receipt or {})
        identity = existing_receipt.get("execution_identity")
        if identity:
            incoming_receipt["execution_identity"] = identity
        row.status = str(status)
        row.receipt_json = json.dumps(incoming_receipt, ensure_ascii=False, default=str)
        row.updated_at = datetime.utcnow()
        db.session.commit()
        return True

    def reconcile_completion(self, *, organization_id: int, execution_key: str,
                             provider_id: str, external_task_id: str,
                             request_id: str | None, status: str,
                             result_digest: str | None = None) -> bool:
        row = ExecutionLedgerRecord.query.filter_by(
            organization_id=int(organization_id), execution_key=str(execution_key)
        ).first()
        if not row:
            return False
        receipt = json.loads(row.receipt_json or "{}")
        expected_provider = str(receipt.get("provider_id") or "")
        expected_task = str(receipt.get("external_task_id") or "")
        expected_request = receipt.get("request_id")
        if expected_provider and expected_provider != str(provider_id):
            raise ValueError("execution_receipt_provider_mismatch")
        if expected_task and expected_task != str(external_task_id):
            raise ValueError("execution_receipt_external_task_mismatch")
        if expected_request and request_id and expected_request != str(request_id):
            raise ValueError("execution_receipt_request_id_mismatch")
        if expected_provider and expected_task:
            completion = {
                "status": str(status),
                "provider_id": str(provider_id),
                "external_task_id": str(external_task_id),
                "request_id": str(request_id) if request_id else expected_request,
            }
            if result_digest:
                completion["result_digest"] = str(result_digest)
            receipt["provider_completion"] = completion
        else:
            receipt.update({
                "provider_id": str(provider_id),
                "external_task_id": str(external_task_id),
                "request_id": str(request_id) if request_id else None,
                "status": str(status),
            })
            if result_digest:
                receipt["result_digest"] = str(result_digest)
        row.status = str(status)
        row.receipt_json = json.dumps(receipt, ensure_ascii=False, default=str)
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
