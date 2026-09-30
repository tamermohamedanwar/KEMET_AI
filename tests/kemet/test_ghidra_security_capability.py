from app.services.ghidra_security_capability import GhidraSecurityCapability


def test_ghidra_is_optional_and_has_no_execution_authority():
    result = GhidraSecurityCapability.assess()
    assert result.status == "optional_not_installed"
    assert result.execution_authority == "none"
    assert result.sandbox_required is True
    assert result.risk_tier == "high"


def test_ghidra_accepts_governed_software_artifacts():
    for input_type in ("binary", "executable", "shared_library", "apk"):
        result = GhidraSecurityCapability.assess(installed=True, version="12.2", input_type=input_type)
        assert result.status == "available_for_governed_analysis"
        assert result.execution_authority == "none"
        assert result.sandbox_required is True
        assert "evidence" in result.outputs
        assert len(result.digest) == 64


def test_ghidra_fails_closed_for_unsupported_input():
    result = GhidraSecurityCapability.assess(installed=True, version="12.2", input_type="unknown")
    assert result.status == "blocked_unsupported_input"


def test_ghidra_snapshot_preserves_governance_boundaries():
    snapshot = GhidraSecurityCapability.snapshot()
    assert snapshot["governance"]["optional"] is True
    assert snapshot["governance"]["no_execution_authority"] is True
    assert snapshot["governance"]["no_mandatory_runtime_dependency"] is True


def test_ghidra_contract_exposes_stable_security_identity():
    snapshot = GhidraSecurityCapability.snapshot()
    assert snapshot["version"] == "1.1"
    assert snapshot["assessment"]["capability"] == "binary_analysis"
    assert snapshot["governance"]["risk_tier"] == "high"
    assert snapshot["governance"]["sandbox_required"] is True


def test_tool_registry_exposes_ghidra_as_non_executing_security_capability():
    from app.services.tool_intelligence_registry import ToolIntelligenceRegistry

    snapshot = ToolIntelligenceRegistry.snapshot(1)
    ghidra = next(item for item in snapshot["tools"] if item["tool_id"] == "ghidra")
    assert "binary_analysis" in ghidra["capabilities"]
    assert ghidra["security_tier"] == "high"
    assert ghidra["provenance"] == "official_nsa_ghidra"
    assert snapshot["governance"]["no_execution_authority"] is True
