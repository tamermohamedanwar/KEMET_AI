from app.services.growth_automation_service import growth_automation_service


def test_growth_catalog_covers_priority_business_automation():
    catalog = growth_automation_service.catalog(1)
    ids = {item["playbook_id"] for item in catalog["playbooks"]}
    assert {"linkedin_comment_leads", "social_engagement_prospects", "seo_prospects"} <= ids
    assert {"youtube_to_linkedin_carousel", "tiktok_engagement", "cross_language_reels"} <= ids
    assert "voice_sales_agent" in ids
    assert catalog["governance"]["external_execution"] is False
    assert catalog["governance"]["human_approval_required"] is True


def test_growth_plan_is_tenant_scoped_and_approval_gated():
    result = growth_automation_service.plan(
        1,
        "seo_prospects",
        target={"market": "Egypt", "service": "SEO"},
        evidence={"source": "public_search_results"},
    )
    assert result["success"] is True
    plan = result["plan"]
    assert plan["approval_required"] is True
    assert plan["execution_authority"] is False
    assert plan["external_execution"] is False
    assert plan["database_mutation"] is False
    assert plan["canonical_runtime_only"] is True
    assert len(plan["plan_digest"]) == 64


def test_growth_plan_fails_closed_for_unknown_playbook():
    result = growth_automation_service.plan(1, "does_not_exist")
    assert result["status"] == "blocked"
    assert result["error"] == "unknown_playbook"


def test_growth_plan_fails_closed_without_organization():
    result = growth_automation_service.plan(None, "seo_prospects")
    assert result["status"] == "blocked"
    assert result["error"] == "organization_required"


def test_command_center_exposes_growth_automation():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    route = (root / "app" / "routes" / "command_center.py").read_text(encoding="utf-8")
    assert "/api/bos/growth-automation" in route
    assert "/api/bos/growth-automation/plan" in route
