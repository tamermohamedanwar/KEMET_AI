from app.services.strix_security_testing_capability import StrixSecurityTestingCapability
from app.services.tool_intelligence_registry import ToolIntelligenceRegistry


def test_strix_requires_authorization():
    assessment = StrixSecurityTestingCapability.assess(installed=True, version="test", authorization_confirmed=False)
    assert assessment.status == "blocked_authorization_required"
    assert assessment.execution_authority == "none"
    assert assessment.risk_tier == "critical"


def test_strix_requires_supported_authorized_target():
    assessment = StrixSecurityTestingCapability.assess(
        installed=True,
        version="test",
        target_type="authorized_staging",
        authorization_confirmed=True,
    )
    assert assessment.status == "available_for_governed_security_testing"
    assert assessment.sandbox_required is True
    assert "proof_of_concept" in assessment.outputs


def test_strix_blocks_unknown_target():
    assessment = StrixSecurityTestingCapability.assess(
        installed=True,
        version="test",
        target_type="internet_target",
        authorization_confirmed=True,
    )
    assert assessment.status == "blocked_unsupported_target"


def test_strix_snapshot_has_governance_boundary():
    snapshot = StrixSecurityTestingCapability.snapshot()
    assert snapshot["governance"]["no_execution_authority"] is True
    assert snapshot["governance"]["authorization_required"] is True
    assert snapshot["governance"]["authorized_targets_only"] is True
    assert snapshot["governance"]["no_mandatory_runtime_dependency"] is True


def test_registry_discovers_strix_without_granting_authority():
    snapshot = ToolIntelligenceRegistry.snapshot(organization_id=1)
    capability_ids = {item["capability_id"] for item in snapshot["capabilities"]}
    tool_ids = {item["tool_id"] for item in snapshot["tools"]}
    assert "validated_application_security_testing" in capability_ids
    assert "strix" in tool_ids
    evaluation = ToolIntelligenceRegistry.evaluate("strix")
    assert evaluation["verified"] is True
    assert evaluation["execution_authority"] == "canonical_runtime_only"
