import pytest

from app.services.voice_call_service import voice_call_service
from app.services.voice_qualification_service import voice_qualification_service


def make_event(state="completed", intent="sales_inquiry", metadata=None):
    return voice_call_service.normalize(
        organization_id=1,
        external_call_id="call-qual-1",
        caller_id="caller-1",
        state=state,
        text="أريد شراء الخدمة",
        intent=intent,
        metadata=metadata,
    )


def test_completed_sales_call_builds_qualification_plan():
    event = make_event(metadata={"qualification": {
        "need": "business automation",
        "budget": "business",
        "timeline": "this month",
        "authority": True,
        "fit": "strong",
    }})

    result = voice_qualification_service.qualify(event)

    assert result["ready"] is True
    assert result["qualification"]["status"] == "qualified"
    assert result["qualification"]["score"] == 100
    assert result["next_step"] == "prepare_follow_up_plan"
    assert result["governance"]["read_only"] is True
    assert result["governance"]["external_execution"] is False
    assert result["commercial"]["causal_claim"] is False


def test_missing_signals_require_more_information():
    result = voice_qualification_service.qualify(
        make_event(metadata={"qualification": {"need": "CRM"}})
    )

    assert result["qualification"]["status"] == "needs_information"
    assert "budget" in result["qualification"]["missing_fields"]
    assert result["next_step"] == "collect_missing_qualification"


def test_non_sales_intent_is_not_sales_ready():
    result = voice_qualification_service.qualify(
        make_event(intent="support_request", metadata={
            "qualification": {"need": "support", "fit": "unknown"}
        })
    )

    assert result["qualification"]["status"] == "not_sales_ready"
    assert result["commercial"]["outcome_candidate"] is True


def test_active_call_cannot_claim_qualification_readiness():
    result = voice_qualification_service.qualify(
        make_event(state="in_progress")
    )

    assert result["ready"] is False
    assert result["qualification"]["status"] == "not_ready"
    assert result["commercial"]["outcome_candidate"] is False
    assert result["governance"]["auto_execute"] is False


def test_explicit_signals_override_event_metadata():
    event = make_event(metadata={"qualification": {"need": "old"}})

    result = voice_qualification_service.qualify(
        event,
        signals={"need": "new"},
    )

    assert result["qualification"]["signals"]["need"] == "new"
