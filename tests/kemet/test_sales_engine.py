from app.core.sales import SalesEngine


def test_sales_engine():
    result = SalesEngine.analyze(
        leads=100,
        qualified_leads=60,
        opportunities=30,
        customers=6,
        pipeline_value=150000,
        average_deal_value=25000,
    )

    assert result["success"] is True
    assert result["engine"] == "kemet_sales"
    assert result["metrics"]["qualification_rate"] == 60.0
    assert result["metrics"]["opportunity_rate"] == 50.0
    assert result["metrics"]["close_rate"] == 20.0


def test_sales_priority():
    result = SalesEngine.analyze(
        leads=100,
        qualified_leads=60,
        opportunities=30,
        pipeline_value=150000,
    )

    assert result["decision"]["priority"] == "high"
    assert result["decision"]["focus"] == "Convert qualified opportunities into customers"


def test_sales_actions_are_governed():
    result = SalesEngine.analyze(
        leads=50,
        qualified_leads=20,
        opportunities=5,
    )

    actions = SalesEngine.build_actions(result)

    assert len(actions) == 1
    assert actions[0]["requires_approval"] is True
    assert actions[0]["external_execution"] is False
