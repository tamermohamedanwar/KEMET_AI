from app.services.campaign_governance_service import CampaignGovernanceService, CampaignPlanRequest


def request(**overrides):
    data = dict(
        organization_id=1,
        campaign_id="first-content-campaign",
        objective="leads",
        audience="Adults seeking verified employment opportunities in Egypt",
        platforms=("facebook", "instagram", "youtube", "tiktok"),
        budget_currency="EGP",
        budget_amount=1000,
        geography="Egypt",
    )
    data.update(overrides)
    return CampaignPlanRequest(**data)


def test_campaign_plan_is_tenant_bound_and_review_only():
    result = CampaignGovernanceService().plan(request())
    assert result["success"] is True
    plan = result["plan"]
    assert plan["schema"] == "kemet.campaign_plan.v1"
    assert plan["organization_id"] == 1
    assert plan["governance"]["status"] == "review_required"
    assert plan["governance"]["external_execution"] is False
    assert plan["governance"]["no_autonomous_budget_spend"] is True
    assert len(plan["plan_digest"]) == 64


def test_campaign_plan_rejects_invalid_platform():
    result = CampaignGovernanceService().plan(request(platforms=("facebook", "unknown")))
    assert result["status"] == "blocked"
    assert result["error"] == "unsupported_campaign_platform"


def test_campaign_plan_rejects_negative_budget():
    result = CampaignGovernanceService().plan(request(budget_amount=-1))
    assert result["status"] == "blocked"
    assert result["error"] == "budget_must_be_non_negative"


def test_campaign_plan_does_not_infer_sensitive_targeting():
    result = CampaignGovernanceService().plan(request())
    assert result["plan"]["targeting"]["no_inferred_sensitive_attributes"] is True
    assert result["plan"]["governance"]["no_sensitive_targeting_inference"] is True
