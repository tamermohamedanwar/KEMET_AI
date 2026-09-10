from app.core.evidence import execution_evidence_fabric


def test_evidence_digest_is_deterministic():
    payload = {"action": "business_insights", "status": "success"}
    assert execution_evidence_fabric.digest(payload) == execution_evidence_fabric.digest(payload)


def test_execution_evidence_contains_governance_facts():
    result = execution_evidence_fabric.execution_record(
        action="refund_request",
        plan_hash="abc123",
        risk={"tier": "critical", "evidence_required": True},
        result={"status": "blocked", "success": False, "executed": False},
    )
    assert result["type"] == "execution_evidence"
    assert result["risk"]["tier"] == "critical"
    assert result["executed"] is False
    assert len(result["digest"]) == 64


def test_evidence_changes_when_execution_status_changes():
    base = execution_evidence_fabric.execution_record(
        action="send_notification",
        plan_hash="abc123",
        risk={"tier": "medium"},
        result={"status": "failed", "success": False, "executed": False},
    )
    changed = execution_evidence_fabric.execution_record(
        action="send_notification",
        plan_hash="abc123",
        risk={"tier": "medium"},
        result={"status": "success", "success": True, "executed": True},
    )
    assert base["digest"] != changed["digest"]
