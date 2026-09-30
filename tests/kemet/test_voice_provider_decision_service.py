from app import create_app
from app.services.voice_provider_decision_service import voice_provider_decision_service
from app.services.mendes.mendes_episode_readiness_service import mendes_episode_readiness_service
from app.services.mendes.mendes_pilot_episode_service import mendes_pilot_episode_service


def test_voice_decision_is_explicit_and_non_executing():
    app = create_app()
    with app.app_context():
        package = mendes_pilot_episode_service.build(1)["package"]
        readiness = {"voice_review": mendes_episode_readiness_service._voice(package)}
        result = voice_provider_decision_service.build(organization_id=1, readiness=readiness)
    assert result["status"] == "DECISION_REQUIRED"
    assert result["selected"] is False
    assert result["decision_contract"]["selection_must_be_explicit"] is True
    assert result["decision_contract"]["selection_does_not_grant_execution_authority"] is True
    assert result["governance"]["execution_authority"] is False
    assert result["governance"]["mcp"] is False
    assert len(result["candidate"]["evidence_digest"]) == 64


def test_voice_candidate_is_not_presented_as_a_purchase_or_authorization():
    app = create_app()
    with app.app_context():
        package = mendes_pilot_episode_service.build(1)["package"]
        readiness = {"voice_review": mendes_episode_readiness_service._voice(package)}
        result = voice_provider_decision_service.build(organization_id=1, readiness=readiness)
    assert result["candidate"]["provider"] == "piper_local"
    assert result["selected"] is False
    assert "purchase" in result["truth_boundary"]
