from app.core.event_ingestion_gateway import EventIngestionGateway
from app.core.event_trigger_plane import EventTriggerPlane, TriggerDefinition


class FakeStore:
    def __init__(self):
        self.keys = set()
        self.next_id = 1

    def append(self, event, *, idempotency_key, trace_id=None):
        key = (event.organization_id, event.source, idempotency_key)
        if key in self.keys:
            return {"accepted": False, "status": "deduplicated", "record_id": 1}
        self.keys.add(key)
        record_id = self.next_id
        self.next_id += 1
        return {"accepted": True, "status": "accepted", "record_id": record_id}


def test_gateway_persists_before_matching_and_preserves_trace():
    plane = EventTriggerPlane()
    plane.register(
        TriggerDefinition(
            trigger_id="lead-hot",
            organization_id=4,
            event_type="lead.hot",
            workflow_id="follow-up",
        )
    )
    gateway = EventIngestionGateway(plane=plane, store=FakeStore())
    result = gateway.ingest(
        organization_id=4,
        event_type="lead.hot",
        payload={"lead_id": 8},
        source="crm",
        idempotency_key="crm-8",
        trace_id="trace-8",
    )
    assert result["accepted"] is True
    assert result["record_id"] == 1
    assert result["trace_id"] == "trace-8"
    assert result["intents"][0]["execution"]["executed"] is False


def test_gateway_deduplicates_by_tenant_source_and_key():
    gateway = EventIngestionGateway(store=FakeStore())
    first = gateway.ingest(
        organization_id=1,
        event_type="order.created",
        source="shop",
        idempotency_key="order-1",
    )
    duplicate = gateway.ingest(
        organization_id=1,
        event_type="order.created",
        source="shop",
        idempotency_key="order-1",
    )
    other_tenant = gateway.ingest(
        organization_id=2,
        event_type="order.created",
        source="shop",
        idempotency_key="order-1",
    )
    assert first["accepted"] is True
    assert duplicate["status"] == "deduplicated"
    assert other_tenant["accepted"] is True


def test_cloud_event_envelope_is_standard_shaped():
    gateway = EventIngestionGateway(store=FakeStore())
    event = gateway.plane.normalize(
        organization_id=7,
        event_type="message.received",
        payload={"text": "hello"},
        source="web",
    )
    envelope = gateway.cloud_event(event)
    assert envelope["specversion"] == "1.0"
    assert envelope["id"] == event.event_id
    assert envelope["type"] == event.event_type
    assert envelope["data"] == event.payload
