from __future__ import annotations

from typing import Any

from app.core.execution_evidence import execution_evidence
from app.core.execution_ledger import execution_ledger


class ExecutionHistoryService:
    VERSION = "1.0"

    def get(self, *, organization_id: int, execution_key: str,
            limit: int = 100) -> dict[str, Any] | None:
        ledger = execution_ledger.get(
            organization_id=organization_id, execution_key=execution_key
        )
        evidence = execution_evidence.history(
            organization_id=organization_id, execution_key=execution_key, limit=limit
        )
        if ledger is None and not evidence:
            return None
        return {
            "organization_id": int(organization_id),
            "execution_key": str(execution_key),
            "ledger": ledger,
            "evidence": evidence,
            "evidence_count": len(evidence),
        }


execution_history = ExecutionHistoryService()
