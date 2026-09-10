from app.core.revenue import RevenueEngine


def test_revenue_engine():
    result = RevenueEngine.analyze(
        leads=100,
        opportunities=20,
        customers=8,
        revenue=50000,
        pipeline_value=120000,
    )

    assert result["success"] is True
    assert result["engine"] == "kemet_revenue"
    assert result["metrics"]["conversion_rate"] == 20.0


def test_revenue_priority():
    result = RevenueEngine.analyze(
        leads=50,
        opportunities=5,
        pipeline_value=100000,
    )

    assert result["decision"]["priority"] == "high"
    assert result["decision"]["focus"] == "Convert pipeline into revenue"


def test_revenue_actions_are_governed():
    result = RevenueEngine.analyze(leads=10, opportunities=2)
    actions = RevenueEngine.build_actions(result)

    assert len(actions) == 1
    assert actions[0]["requires_approval"] is True
