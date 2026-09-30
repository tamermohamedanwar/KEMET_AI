from wsgi import application
from app.services.workforce_outcome_learning import workforce_outcome_learning


def test_recommendation_is_policy_bound_and_non_executing():
    with application.app_context():
        result = workforce_outcome_learning.recommend(
            1, objective="Improve lead conversion", action="lead_scoring"
        )
        assert result["success"] is True
        assert result["status"] == "RECOMMENDATION_READY"
        assert result["execution"] is False
        assert result["approval_required"] is True
        assert result["governance"]["ranking_adjustment"] == "recommendation_only"
        assert result["recommended"]["action_policy"] in {"allow", "ask"}


def test_unknown_action_fails_closed():
    with application.app_context():
        result = workforce_outcome_learning.recommend(
            1, objective="Unsafe", action="unknown_action"
        )
        assert result["success"] is False
        assert result["status"] == "BLOCKED"


def test_snapshot_is_observational_and_digest_bound():
    with application.app_context():
        result = workforce_outcome_learning.learning_snapshot(1, period="30d")
        assert result["success"] is True
        assert result["schema"] == "kemet.workforce_outcome_learning.v1"
        assert result["governance"]["causal_claim"] is False
        assert result["governance"]["roi_claim"] is False
        assert result["governance"]["auto_execute"] is False
        assert len(result["snapshot_digest"]) == 64


def test_snapshot_tenant_requirement_fails_closed():
    with application.app_context():
        result = workforce_outcome_learning.learning_snapshot(0)
        assert result["status"] == "BLOCKED"
