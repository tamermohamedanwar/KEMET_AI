from app.services.tool_intelligence_registry import ToolIntelligenceRegistry


def test_ml_evaluation_is_registered_as_non_execution_capability():
    capability_ids = {item.capability_id for item in ToolIntelligenceRegistry.CAPABILITIES}
    assert "ml_evaluation" in capability_ids


def test_ml_evaluation_registry_candidate_is_governed():
    matches = [tool for tool in ToolIntelligenceRegistry.TOOLS if "ml_evaluation" in tool.capabilities]
    assert matches
    assert all(tool.security_tier in {"high", "medium"} for tool in matches)
    assert all(tool.provenance.startswith("official_") or tool.provenance == "internal_kemet" for tool in matches)
