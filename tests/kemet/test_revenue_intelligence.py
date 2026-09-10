from app import create_app
from app.services.revenue_intelligence_service import RevenueIntelligenceService


def test_revenue_intelligence_is_read_only():
    app = create_app()
    with app.app_context():
        result = RevenueIntelligenceService.overview(1)

    assert result["database_mutation"] is False
    assert result["external_execution"] is False
    assert result["auto_execute"] is False
    assert result["causal_attribution"] is False


def test_revenue_metrics_are_consistent():
    app = create_app()
    with app.app_context():
        result = RevenueIntelligenceService.overview(1, previous_active=10)

    assert result["active_subscriptions"] >= 0
    assert result["mrr"] >= 0
    assert result["arr"] == round(result["mrr"] * 12, 2)
    if result["active_subscriptions"]:
        assert result["arpu"] == round(
            result["mrr"] / result["active_subscriptions"], 2
        )
    assert result["churn_rate"] >= 0
    assert result["churn_basis"] == "previous_period_active_baseline"
    assert isinstance(result["plan_mix"], dict)
