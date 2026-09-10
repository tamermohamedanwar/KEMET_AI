from app.core.decision.decision_engine import DecisionEngine


def context(**business):
    return {
        "tenant": {
            "organization_id": 1,
            "user_id": 1,
        },
        "business": business,
        "mode": "advisory",
        "approval_required": True,
        "external_execution": False,
        "database_mutation": False,
    }


def test_weighted_decision_engine():
    engine = DecisionEngine()

    result = engine.decide(
        "review my business",
        context(
            revenue=1000,
            leads=20,
            qualified_leads=8,
            converted_leads=1,
            customers=1,
            open_tickets=2,
            automation_executions=100,
            successful_executions=98,
        ),
    )

    assert result["success"] is True
    assert result["engine"] == "kemet_decision_engine"
    assert result["version"] == "2.0"
    assert result["requires_approval"] is True
    assert result["external_execution"] is False
    assert result["database_mutation"] is False
    assert result["decision"]["impact_score"] >= 0
    assert result["decision"]["urgency_score"] >= 0


def test_live_data_changes_decision():
    engine = DecisionEngine()

    customer_pressure = engine.decide(
        "review my business",
        context(
            revenue=1000,
            leads=2,
            qualified_leads=0,
            converted_leads=0,
            customers=1,
            open_tickets=40,
            automation_executions=100,
            successful_executions=98,
        ),
    )

    sales_pressure = engine.decide(
        "review my business",
        context(
            revenue=1000,
            leads=20,
            qualified_leads=10,
            converted_leads=0,
            customers=1,
            open_tickets=1,
            automation_executions=100,
            successful_executions=98,
        ),
    )

    assert customer_pressure["decision"]["area"] == "customer"
    assert sales_pressure["decision"]["area"] in {"sales", "growth", "revenue"}
    assert customer_pressure["decision"]["area"] != sales_pressure["decision"]["area"]


def test_intent_weighting():
    engine = DecisionEngine()

    result = engine.decide(
        "sales pipeline",
        context(
            revenue=5000,
            leads=5,
            qualified_leads=2,
            converted_leads=0,
            customers=1,
            open_tickets=30,
            automation_executions=100,
            successful_executions=99,
        ),
    )

    assert result["success"] is True
    assert result["decision"]["area"] == "sales"
    assert result["requires_approval"] is True
    assert result["external_execution"] is False
    assert result["database_mutation"] is False
