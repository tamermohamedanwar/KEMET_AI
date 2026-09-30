from app.services.commerce_revenue_workflow_service import commerce_revenue_workflow_service


def test_qualified_commerce_workflow_reaches_approval():
    result = commerce_revenue_workflow_service.build_plan(
        organization_id=1,
        product={"name": "Kemet Demo Product", "features": ["verified feature"]},
        qualification={"status": "qualified", "missing_fields": [], "score": 90},
        lead_id=6,
        channel="whatsapp",
    )
    assert result["status"] == "approval_required"
    assert result["follow_up"]["action"] == "sales_follow_up"
    assert result["follow_up"]["approval"]["required"] is True
    assert result["governance"]["external_execution"] is False


def test_unqualified_commerce_workflow_stops_before_approval():
    result = commerce_revenue_workflow_service.build_plan(
        organization_id=1,
        product={"name": "Kemet Demo Product"},
        qualification={"status": "needs_information", "missing_fields": ["budget"]},
        lead_id=6,
    )
    assert result["status"] == "blocked"
    assert result["follow_up"]["status"] == "blocked"


def test_commerce_workflow_does_not_claim_revenue_or_roi():
    result = commerce_revenue_workflow_service.build_plan(
        organization_id=1,
        product={"name": "Kemet Demo Product"},
        qualification={"status": "qualified", "missing_fields": []},
    )
    assert result["commercial"]["revenue"] == "not_available"
    assert result["commercial"]["roi"] == "not_proven"
    assert result["commercial"]["causal_claim"] is False
