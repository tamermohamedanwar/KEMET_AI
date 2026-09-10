from app.core.integration import KemetActivationService


def test_activation_status():
    service = KemetActivationService()
    result = service.status()

    assert result["ok"] is True
    assert result["mode"] == "advisory"
    assert len(result["connected_engines"]) == 7
    assert result["approval_required"] is True
    assert result["external_execution"] is False
    assert result["database_mutation"] is False


def test_activation_analysis():
    service = KemetActivationService()

    result = service.analyze(
        revenue_data={
            "leads": 100,
            "opportunities": 20,
            "customers": 5,
            "revenue": 50000,
            "pipeline_value": 150000,
        },
        sales_data={
            "leads": 100,
            "qualified_leads": 60,
            "opportunities": 20,
            "customers": 5,
            "pipeline_value": 150000,
        },
        customer_data={
            "customer_id": "demo",
            "channel": "web",
            "message": "hello",
        },
        analytics_data={
            "revenue": 50000,
            "cost": 10000,
            "customers": 5,
            "leads": 100,
            "automated_tasks": 40,
            "manual_hours_saved": 20,
        },
    )

    assert result["ok"] is True
    assert "revenue" in result
    assert "sales" in result
    assert "customer" in result
    assert "analytics" in result
    assert "intelligence" in result


def test_activation_governance():
    service = KemetActivationService()

    result = service.run(
        revenue_data={"revenue": 100000, "pipeline_value": 200000},
        sales_data={"leads": 50, "customers": 5},
    )

    assert result["ok"] is True
    assert result["status"] == "waiting_approval"
    assert result["approval_required"] is True
    assert result["external_execution"] is False
    assert result["database_mutation"] is False
    assert result["plan"]["requires_approval"] is True
