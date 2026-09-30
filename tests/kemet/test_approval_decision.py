import pytest
from app.core.approval_decision import decide_approval, verify_approval
from app.core.approval_package import build_approval_package
from app.core.plan_context import PlanContext, bind_plan_context
from app.core.plan_risk import assess_plan_risk
from app.core.task_planner import TaskPlanningEngine

def package_for(prompt="build a website", org=1):
    plan = TaskPlanningEngine().plan(prompt, organization_id=org)
    binding = bind_plan_context(plan, PlanContext(organization_id=org))
    return build_approval_package(plan, binding, assess_plan_risk(plan))

def test_approval_round_trip():
    package = package_for()
    decision = decide_approval(package, 7, True)
    assert decision.decision == "approved"
    assert verify_approval(package, decision)

def test_rejection_requires_reason():
    package = package_for()
    with pytest.raises(ValueError, match="rejection_reason_required"):
        decide_approval(package, 7, False)

def test_tampered_package_or_decision_fails_closed():
    package = package_for()
    decision = decide_approval(package, 7, True)
    assert not verify_approval(package_for("send an update"), decision)
    assert not verify_approval(package, decision.__class__(**{**decision.as_dict(), "decision_hash": "x"}))
