from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from app import db
from app.models.automation_event import AutomationEventRecord


class DurableEventStore:
    """Persistent event ledger with tenant-scoped idempotency."""

    VERSION = "1.0"

    @staticmethod
    def _dt(value: str | None) -> datetime:
        if not value:
            return datetime.utcnow()
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    def append(self, event: Any, *, idempotency_key: str | None = None,
               trace_id: str | None = None) -> dict[str, Any]:
        key = str(idempotency_key or event.event_id).strip()
        existing = AutomationEventRecord.query.filter_by(
            organization_id=event.organization_id,
            source=event.source,
            idempotency_key=key,
        ).first()
        if existing:
            return {"accepted": False, "status": "deduplicated", "record_id": existing.id}

        record = AutomationEventRecord(
            organization_id=event.organization_id,
            event_id=event.event_id,
            event_type=event.event_type,
            source=event.source,
            idempotency_key=key,
            correlation_id=event.correlation_id,
            trace_id=trace_id,
            payload_json=json.dumps(event.payload, ensure_ascii=False, default=str),
            status="accepted",
            occurred_at=self._dt(event.occurred_at),
            received_at=datetime.utcnow(),
        )
        db.session.add(record)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            existing = AutomationEventRecord.query.filter_by(
                organization_id=event.organization_id,
                source=event.source,
                idempotency_key=key,
            ).first()
            if existing:
                return {"accepted": False, "status": "deduplicated", "record_id": existing.id}
            raise
        return {"accepted": True, "status": "accepted", "record_id": record.id}

    def mark_processing(self, record_id: int) -> bool:
        record = db.session.get(AutomationEventRecord, int(record_id))
        if not record or record.status in {"completed", "dead_letter"}:
            return False
        record.status = "processing"
        record.attempts += 1
        db.session.commit()
        return True

    def complete(self, record_id: int) -> bool:
        record = db.session.get(AutomationEventRecord, int(record_id))
        if not record:
            return False
        record.status = "completed"
        record.processed_at = datetime.utcnow()
        record.last_error = None
        db.session.commit()
        return True

    def fail(self, record_id: int, error: str, *, dead_letter: bool = False) -> bool:
        record = db.session.get(AutomationEventRecord, int(record_id))
        if not record:
            return False
        record.status = "dead_letter" if dead_letter else "failed"
        record.last_error = str(error)[:10000]
        record.processed_at = datetime.utcnow()
        db.session.commit()
        return True


durable_event_store = DurableEventStore()
