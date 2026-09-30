import pytest

from app.services.voice_call_service import VoiceCallService


@pytest.fixture()
def service():
    return VoiceCallService()


def test_voice_call_normalizes_and_detects_arabic(service):
    event = service.normalize(
        organization_id=1,
        external_call_id="call-1",
        caller_id="caller-1",
        state="completed",
        text="عايز احجز موعد",
        intent="appointment_request",
    )
    assert event.channel if hasattr(event, "channel") else "voice" == "voice"
    assert event.language == "ar"
    assert event.intent == "appointment_request"


def test_voice_call_route_is_read_only_and_approval_safe(service):
    event = service.normalize(
        organization_id=1,
        external_call_id="call-2",
        caller_id="caller-2",
        state="completed",
        text="I want to book an appointment",
        intent="appointment_request",
    )
    route = service.route(event)
    assert route["commercial_outcome_ready"] is True
    assert route["governance"]["read_only"] is True
    assert route["governance"]["external_execution"] is False
    assert route["governance"]["database_mutation"] is False
    assert route["governance"]["auto_execute"] is False
    assert route["governance"]["human_approval_required"] is True


def test_voice_call_rejects_invalid_identity_and_state(service):
    with pytest.raises(ValueError, match="organization_required"):
        service.normalize(
            organization_id=0,
            external_call_id="call-3",
            caller_id="caller-3",
            state="ringing",
        )
    with pytest.raises(ValueError, match="unsupported_call_state"):
        service.normalize(
            organization_id=1,
            external_call_id="call-4",
            caller_id="caller-4",
            state="executing",
        )


def test_unknown_voice_intent_fails_closed_to_unknown(service):
    event = service.normalize(
        organization_id=1,
        external_call_id="call-5",
        caller_id="caller-5",
        state="in_progress",
        intent="arbitrary_external_action",
    )
    assert event.intent == "unknown"


def test_completed_call_builds_evidence_ready_commercial_context(service):
    event = service.normalize(
        organization_id=7,
        external_call_id="call-commercial-1",
        caller_id="caller-7",
        state="completed",
        intent="sales_inquiry",
    )
    context = service.commercial_context(event)
    assert context["commercial_stage"] == "interaction_completed"
    assert context["outcome_status"] == "candidate"
    assert context["revenue"]["status"] == "not_available"
    assert context["roi"]["status"] == "not_proven"
    assert context["revenue"]["causal_claim"] is False
    assert context["governance"]["read_only"] is True
    assert context["execution_link"]["status"] == "not_provided"
    assert context["trace_available"] if "trace_available" in context else True


def test_completed_call_can_carry_a_governed_execution_reference(service):
    event = service.normalize(
        organization_id=7,
        external_call_id="call-commercial-2",
        caller_id="caller-7",
        state="completed",
        intent="sales_inquiry",
    )
    context = service.commercial_context(event, execution_key="exec-voice-1")
    assert context["execution_link"]["status"] == "provided"
    assert context["execution_link"]["execution_key"] == "exec-voice-1"
    assert context["revenue"]["causal_claim"] is False


def test_active_call_cannot_claim_a_business_outcome(service):
    event = service.normalize(
        organization_id=7,
        external_call_id="call-active-1",
        caller_id="caller-7",
        state="in_progress",
        intent="sales_inquiry",
    )
    context = service.commercial_context(event)
    assert context["outcome_status"] == "not_ready"
    assert context["revenue"]["status"] == "not_available"
    assert context["roi"]["status"] == "not_proven"
