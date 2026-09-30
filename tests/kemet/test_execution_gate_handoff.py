from app.core.approval_decision import decide_approval
from app.core.approval_package import ApprovalPackage
from app.core.central_gate_handoff import GateHandoff
from app.core.execution.central_gate import CentralExecutionGate
from app.core.execution.authorization import execution_authorization


def make_handoff(plan, action="business_insights", execution_key="exec-1"):
    plan_hash = execution_authorization.plan_hash(plan)
    package = ApprovalPackage(
        organization_id=1, plan_hash=plan_hash, context_fingerprint="ctx-1",
        risk_level="low", risk_score=0, approval_required=True,
        external_side_effects=False, database_mutation=False,
        affected_resources=(), reasons=(),
        evidence_requirements=("decision", "plan", "risk_assessment"),
        package_hash="pkg-1",
    )
    decision = decide_approval(package, 7, True)
    payload = {
        "organization_id": 1, "plan_hash": plan_hash,
        "context_fingerprint": "ctx-1", "package_hash": package.package_hash,
        "decision_hash": decision.decision_hash, "approver_id": 7,
        "action": action, "execution_key": execution_key,
        "status": "approved_for_gate",
    }
    import hashlib, json
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return GateHandoff(handoff_hash=digest, **payload)


def test_gate_rejects_missing_handoff():
    result = CentralExecutionGate().authorize_with_handoff({}, {}, None, "x", "k")
    assert result["error"] == "gate_handoff_required"


def test_gate_rejects_plan_mismatch():
    plan = {"plan_id": "p1", "action": "business_insights", "value": 1}
    handoff = make_handoff(plan)
    changed = dict(plan, value=2)
    result = CentralExecutionGate().authorize_with_handoff(
        changed, {"token": "x"}, handoff, "business_insights", "exec-1"
    )
    assert result["error"] == "gate_plan_mismatch"


def test_gate_rejects_invalid_handoff_binding():
    plan = {"plan_id": "p1", "action": "business_insights", "value": 1}
    handoff = make_handoff(plan)
    result = CentralExecutionGate().authorize_with_handoff(
        plan, {"token": "x"}, handoff, "refund", "exec-1"
    )
    assert result["error"] == "gate_handoff_invalid"


def test_gate_rejects_tenant_mismatch():
    plan = {"plan_id": "p1", "organization_id": 2, "action": "business_insights"}
    handoff = make_handoff(plan)
    result = CentralExecutionGate().authorize_with_handoff(
        plan, {"token": "x"}, handoff, "business_insights", "exec-1"
    )
    assert result["error"] == "gate_tenant_mismatch"


def test_gate_rejects_context_mismatch():
    plan = {"plan_id": "p1", "action": "business_insights"}
    handoff = make_handoff(plan)
    result = CentralExecutionGate().authorize_with_handoff(
        plan, {"token": "x"}, handoff, "business_insights", "exec-1", "ctx-2"
    )
    assert result["error"] == "gate_context_mismatch"
