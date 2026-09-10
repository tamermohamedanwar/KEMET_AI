from app.core.event_trigger_plane import (
    AutomationEvent,
    EventTriggerPlane,
    TriggerDefinition,
)


def test_event_matches_tenant_scoped_trigger():
    plane = EventTriggerPlane()
    plane.register(
        TriggerDefinition(
            trigger_id="lead-hot",
            organization_id=1,
            event_type="lead.hot",
            workflow_id="sales-followup",
            conditions={"priority": "high"},
        )
    )
    result = plane.publish(
        organization_id=1,
        event_type="lead.hot",
        payload={"priority": "high", "lead_id": 42},
    )
    assert result["accepted"] is True
    assert result["status"] == "matched"
    assert result["intents"][0]["workflow_id"] == "sales-followup"
    assert result["intents"][0]["execution"]["executed"] is False


def test_cross_tenant_trigger_is_not_matched():
    plane = EventTriggerPlane()
    plane.register(
        TriggerDefinition(
            trigger_id="org-one",
            organization_id=1,
            event_type="lead.hot",
            workflow_id="private-workflow",
        )
    )
    result = plane.publish(
        organization_id=2,
        event_type="lead.hot",
        payload={},
    )
    assert result["status"] == "accepted_no_match"
    assert result["intents"] == []


def test_duplicate_event_is_deduplicated():
    plane = EventTriggerPlane()
    plane.register(
        TriggerDefinition(
            trigger_id="ticket",
            organization_id=1,
            event_type="ticket.created",
            workflow_id="ticket-triage",
        )
    )
    first = plane.publish(
        organization_id=1,
        event_type="ticket.created",
        event_id="evt-1",
        payload={"ticket_id": 7},
    )
    second = plane.publish(
        organization_id=1,
        event_type="ticket.created",
        event_id="evt-1",
        payload={"ticket_id": 7},
    )
    assert first["accepted"] is True
    assert second["accepted"] is False
    assert second["status"] == "deduplicated"


def test_invalid_event_is_rejected():
    plane = EventTriggerPlane()
    try:
        plane.normalize(organization_id=1, event_type="", payload={})
    except ValueError as exc:
        assert str(exc) == "event_type_required"
    else:
        raise AssertionError("Expected event_type_required")


def test_event_is_provider_neutral():
    plane = EventTriggerPlane()
    event = plane.normalize(
        organization_id=3,
        event_type="message.received",
        payload={"text": "مرحبا"},
        source="whatsapp",
        correlation_id="conversation-9",
    )
    assert isinstance(event, AutomationEvent)
    assert event.source == "whatsapp"
    assert event.correlation_id == "conversation-9"
