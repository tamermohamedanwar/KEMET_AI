from app.services.creative_engineering_intelligence_service import (
    CreativeEngineeringIntelligenceService,
)


def test_catalog_contains_game_and_agent_sources():
    catalog = CreativeEngineeringIntelligenceService.catalog()
    ids = {item["source_id"] for item in catalog}
    assert "oss-games-index" in ids
    assert "gamedev-agent-skills" in ids
    assert all(item["execution_authority"] is False for item in catalog)


def test_transfer_maps_game_capabilities_to_kemet_domains():
    result = CreativeEngineeringIntelligenceService.transfer("procedural_generation")
    assert result["known"] is True
    assert "content_variants" in result["mapped_kemet_domains"]
    assert result["execution_authority"] is False
    assert result["human_approval_required"] is True


def test_transfer_unknown_is_fail_closed():
    result = CreativeEngineeringIntelligenceService.transfer("unknown_capability")
    assert result["known"] is False
    assert result["mapped_kemet_domains"] == []
    assert result["execution_authority"] is False


def test_harvest_plan_is_governed_and_license_aware():
    result = CreativeEngineeringIntelligenceService.plan_harvest(
        ["game_ai", "procedural_generation", "qa"]
    )
    assert result["schema"] == "kemet.creative_engineering_intelligence.v1"
    assert result["selected_sources"]
    assert result["security_review_required"] is True
    assert result["license_review_required"] is True
    assert result["human_approval_required"] is True
    assert result["external_execution"] is False
    assert result["canonical_executor"] == "kemet"
