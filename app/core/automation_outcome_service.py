from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app import db
from app.models.automation_outcome import AutomationOutcome


class AutomationOutcomeService:
    VERSION = "1.0"

    def record(self, *, organization_id: int, status: str, executed: bool = False,
               job_id: int | None = None, workflow_id: str | None = None,
               event_id: str | None = None, started_at: datetime | None = None,
               retry_count: int = 0, cost_amount: float | None = None,
               currency: str | None = None, business_outcome: str | None = None,
               correlation_id: str | None = None, trace_id: str | None = None,
               receipt: dict[str, Any] | None = None, error_type: str | None = None) -> dict[str, Any]:
        duration_ms = None
        if started_at is not None:
            duration_ms = max(0, int((datetime.utcnow() - started_at).total_seconds() * 1000))
        outcome = AutomationOutcome(
            organization_id=organization_id,
            job_id=job_id,
            workflow_id=workflow_id,
            event_id=event_id,
            status=status,
            executed=executed,
            duration_ms=duration_ms,
            retry_count=max(0, retry_count),
            cost_amount=cost_amount,
            currency=currency,
            business_outcome=business_outcome,
            correlation_id=correlation_id,
            trace_id=trace_id,
            receipt_json=json.dumps(receipt or {}, ensure_ascii=False, default=str),
            error_type=error_type,
        )
        db.session.add(outcome)
        db.session.commit()
        return {
            "outcome_id": outcome.id,
            "status": outcome.status,
            "executed": outcome.executed,
            "duration_ms": outcome.duration_ms,
        }


automation_outcome_service = AutomationOutcomeService()
