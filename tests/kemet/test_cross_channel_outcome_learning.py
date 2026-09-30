from app import create_app
from app.services.cross_channel_outcome_learning import cross_channel_outcome_learning


def test_cross_channel_learning_is_observational_and_fail_closed(monkeypatch):
    app = create_app()
    with app.app_context():
        blocked = cross_channel_outcome_learning.build(0)
        assert blocked["status"] == "BLOCKED"
        assert blocked["governance"]["external_execution"] is False

        monkeypatch.setattr(
            "app.services.cross_channel_outcome_learning.workforce_outcome_learning.learning_snapshot",
            lambda organization_id, period="30d": {
                "status": "LEARNING_SNAPSHOT_READY",
                "snapshot_digest": "snapshot-1",
                "decision_learning": {"count": 0},
            },
        )
        monkeypatch.setattr(
            "app.services.cross_channel_outcome_learning.commercial_outcome_trace.get",
            lambda organization_id, execution_key: None,
        )
        result = cross_channel_outcome_learning.build(1, execution_keys=["missing"], period="30d")

    assert result["success"] is True
    assert result["status"] == "LEARNING_READY"
    assert result["learning"]["cross_channel_comparison"] == "descriptive_only"
    assert result["learning"]["ranking_adjustment"] == "recommendation_only"
    assert result["learning"]["next_action"] == "collect_more_real_outcomes"
    assert len(result["learning_digest"]) == 64


def test_cross_channel_learning_preserves_observed_revenue_and_channel(monkeypatch):
    app = create_app()
    trace = {
        "trace": {"channel": "telegram"},
        "business": {
            "outcome": "completed",
            "revenue": {"amount": 100, "currency": "EGP", "evidence_backed": True},
            "payment": {"evidence_backed": True},
            "delivery": {"evidence_backed": True},
            "roi": None,
        },
        "measurement": {"causal_claim": False},
    }
    with app.app_context():
        monkeypatch.setattr(
            "app.services.cross_channel_outcome_learning.commercial_outcome_trace.get",
            lambda organization_id, execution_key: trace,
        )
        monkeypatch.setattr(
            "app.services.cross_channel_outcome_learning.workforce_outcome_learning.learning_snapshot",
            lambda organization_id, period="30d": {
                "status": "LEARNING_SNAPSHOT_READY",
                "snapshot_digest": "snapshot-2",
                "decision_learning": {"count": 1},
            },
        )
        result = cross_channel_outcome_learning.build(1, execution_keys=["exec-1"])

    assert result["channels"]["telegram"]["observed"] == 1
    assert result["channels"]["telegram"]["revenue_evidence"] == 1
    assert result["traces"][0]["channel"] == "telegram"
    assert result["traces"][0]["payment_observed"] is True
    assert result["traces"][0]["revenue"]["amount"] == 100
    assert result["traces"][0]["causal_claim"] is False
