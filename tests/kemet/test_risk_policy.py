from app.core.execution.risk_policy import execution_risk_policy
from app.core.execution.governed_executor import governed_execution_service


def test_risk_policy_classifies_direct_safe_as_low():
    result = execution_risk_policy.controls("business_insights", "direct_safe")
    assert result["tier"] == "low"
    assert result["human_approval_required"] is False
    assert result["runtime_authorization_required"] is True


def test_risk_policy_classifies_refund_as_critical():
    result = execution_risk_policy.controls("refund_request", "approval_required")
    assert result["tier"] == "critical"
    assert result["human_approval_required"] is True


def test_risk_policy_fails_closed_for_unknown_action():
    result = execution_risk_policy.controls("unknown_action", "blocked")
    assert result["tier"] == "critical"
    assert result["human_approval_required"] is True


def test_governed_runtime_exposes_risk_metadata():
    assert governed_execution_service._risk("business_insights", "direct_safe")["tier"] == "low"
    assert governed_execution_service._risk("refund_request", "approval_required")["tier"] == "critical"


def test_risk_policy_requires_evidence_for_side_effects():
    result = execution_risk_policy.controls("send_notification", "approval_required")
    assert result["evidence_required"] is True
    assert result["attestation_required"] is False


def test_risk_policy_requires_attestation_for_critical_actions():
    result = execution_risk_policy.controls("refund_request", "approval_required")
    assert result["evidence_required"] is True
    assert result["attestation_required"] is True
