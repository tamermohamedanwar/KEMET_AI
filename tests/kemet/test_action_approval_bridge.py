from app.core.execution import ActionApprovalBridge

def decision():
    return {
        "decision": {
            "decision_id": "d1",
            "area": "customer",
            "priority": "critical",
            "title": "Reduce unresolved customer workload",
            "recommended_action": "Review unresolved customer tickets",
            "confidence": 0.8,
        }
    }

def context():
    return {
        "business": {
            "revenue": 8290.76,
            "leads": 1,
            "open_tickets": 40,
            "customers": 1,
        }
    }

def test_plan_waits_for_approval():
    result = ActionApprovalBridge().build_plan("review business", decision(), context())
    assert result["status"] == "waiting_approval"
    assert result["approval"]["required"] is True
    assert result["execution"]["allowed"] is False

def test_gate_blocks_without_approval():
    bridge = ActionApprovalBridge()
    plan = bridge.build_plan("review business", decision(), context())["plan"]
    result = bridge.approve_and_prepare(plan)
    assert result["status"] == "waiting_approval"
    assert result["executed"] is False

def test_approval_does_not_execute_automatically():
    bridge = ActionApprovalBridge()
    plan = bridge.build_plan("review business", decision(), context())["plan"]
    result = bridge.approve_and_prepare(plan, approved=True, approver_id=1)
    assert result["status"] == "approved"
    assert result["executed"] is False
    assert result["external_execution"] is False
    assert result["database_mutation"] is False
