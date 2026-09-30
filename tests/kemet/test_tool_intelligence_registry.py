from app.services.tool_intelligence_registry import tool_intelligence_registry


def test_registry_is_discovery_only():
    snapshot = tool_intelligence_registry.snapshot(7)
    assert snapshot["purpose"] == "task_tool_discovery"
    assert snapshot["governance"]["discovery_only"] is True
    assert snapshot["governance"]["no_execution_authority"] is True
    assert snapshot["governance"]["canonical_runtime_required_for_execution"] is True


def test_registry_has_core_capabilities_and_fallbacks():
    snapshot = tool_intelligence_registry.snapshot(7)
    capabilities = {item["capability_id"] for item in snapshot["capabilities"]}
    assert {"text_generation", "image_generation", "video_generation", "analytics", "coding"} <= capabilities
    youtube = next(item for item in snapshot["tools"] if item["tool_id"] == "youtube_analytics")
    assert "youtube_data" in youtube["fallback_ids"]
    openrouter = next(item for item in snapshot["tools"] if item["tool_id"] == "openrouter")
    assert openrouter["fallback_ids"]


def test_recommendation_is_capability_based_and_provenance_aware():
    result = tool_intelligence_registry.recommend("analytics", 7)
    assert result["organization_id"] == 7
    assert result["recommendations"]
    assert result["selection_policy"]["verified_provenance_required"] is True


def test_unknown_tool_fails_closed():
    assert tool_intelligence_registry.evaluate("does-not-exist")["verified"] is False
