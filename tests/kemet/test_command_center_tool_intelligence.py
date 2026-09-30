from app.services.tool_intelligence_registry import tool_intelligence_registry


def test_tool_intelligence_is_advisory_only():
    result = tool_intelligence_registry.recommend("analytics", organization_id=1)
    assert result["organization_id"] == 1
    assert result["selection_policy"]["verified_provenance_required"] is True
    assert result["selection_policy"]["security_trust_before_cost"] is True


def test_unknown_tool_fails_closed():
    result = tool_intelligence_registry.evaluate("unknown-tool")
    assert result == {"tool_id": "unknown-tool", "status": "unknown", "verified": False}


def test_registry_does_not_grant_execution_authority():
    result = tool_intelligence_registry.evaluate("youtube_analytics")
    assert result["execution_authority"] == "canonical_runtime_only"
    assert result["verified"] is True

