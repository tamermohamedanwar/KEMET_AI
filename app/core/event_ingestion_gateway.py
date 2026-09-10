from __future__ import annotations

from typing import Any

from app.core.durable_event_store import durable_event_store
from app.core.event_trigger_plane import EventTriggerPlane, AutomationEvent


class EventIngestionGateway:
    """Durable ingress boundary: persist first, then match triggers."""

    VERSION = "1.0"

    def __init__(self, plane: EventTriggerPlane | None = None, store: Any = None) -> None:
        self.plane = plane or EventTriggerPlane()
        self.store = store or durable_event_store

    def ingest(
        self,
        *,
        organization_id: int,
        event_type: str,
        payload: dict[str, Any] | None = None,
        source: str = "internal",
        event_id: str | None = None,
        idempotency_key: str | None = None,
        correlation_id: str | None = None,
        trace_id: str | None = None,
    ) -> dict[str, Any]:
        event = self.plane.normalize(
            organization_id=organization_id,
            event_type=event_type,
            payload=payload,
            event_id=event_id,
            source=source,
            correlation_id=correlation_id,
        )
        stored = self.store.append(
            event,
            idempotency_key=idempotency_key or event.event_id,
            trace_id=trace_id,
        )
        if not stored.get("accepted"):
            return {
                "accepted": False,
                "status": "deduplicated",
                "event": event.canonical(),
                "record_id": stored.get("record_id"),
                "intents": [],
            }
        matched = self.plane.ingest(event)
        matched["record_id"] = stored.get("record_id")
        matched["trace_id"] = trace_id
        return matched

    @staticmethod
    def cloud_event(event: AutomationEvent) -> dict[str, Any]:
        """Expose a CloudEvents-compatible envelope without coupling to a broker."""
        return {
            "specversion": "1.0",
            "id": event.event_id,
            "type": event.event_type,
            "source": event.source,
            "subject": str(event.organization_id),
            "time": event.occurred_at,
            "data": event.payload,
        }


event_ingestion_gateway = EventIngestionGateway()
