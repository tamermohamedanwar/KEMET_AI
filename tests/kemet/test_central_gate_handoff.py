from app.core.approval_decision import decide_approval
from app.core.approval_package import build_approval_package
from app.core.central_gate_handoff import create_gate_handoff, verify_gate_handoff
from app.core.plan_context import PlanContext, bind_plan_context
from app.core.plan_risk import assess_plan_risk
from app.core.task_planner import TaskPlanningEngine


def build_fixture():
    plan = TaskPlanningEngine().plan(
        "build a website", organization_id=1, task_id="gate-1"
    )
    binding = bind_plan_context(plan, PlanContext(organization_id=1, user_id=7))
    assessment = assess_plan_risk(plan)
    package = build_approval_package(plan, binding, assessment)
    decision = decide_approval(package, 7, True)
    handoff = create_gate_handoff(
        package, decision, action="business_insights", execution_key="exec-1"
    )
    return package, decision, handoff


def test_gate_handoff_requires_verified_human_approval():
    package, decision, handoff = build_fixture()
    assert handoff.status == "approved_for_gate"
    assert verify_gate_handoff(handoff, organization_id=1, plan_hash=package.plan_hash)


def test_gate_handoff_rejects_unapproved_decision():
    package = build_fixture()[0]
    decision = decide_approval(package, 7, False, "review required")
    try:
        create_gate_handoff(
            package, decision, action="business_insights", execution_key="exec-1"
        )
    except ValueError as exc:
        assert str(exc) == "approval_verification_failed"
    else:
        raise AssertionError("rejected decision must not reach gate")


def test_gate_handoff_binding_fails_closed():
    package, _, handoff = build_fixture()
    assert not verify_gate_handoff(handoff, organization_id=2)
    assert not verify_gate_handoff(handoff, action="refund")
    assert not verify_gate_handoff(handoff, execution_key="exec-2")
    assert not verify_gate_handoff(handoff, plan_hash="wrong")


def test_gate_handoff_tamper_fails_closed():
    _, _, handoff = build_fixture()
    object.__setattr__(handoff, "approver_id", 99)
    assert not verify_gate_handoff(handoff)
