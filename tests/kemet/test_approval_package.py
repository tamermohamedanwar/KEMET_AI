from app.core.approval_package import build_approval_package
from app.core.plan_risk import assess_plan_risk
from app.core.task_planner import TaskPlanningEngine
from app.core.plan_context import PlanContext, bind_plan_context


def test_approval_package_is_bound_and_deterministic():
    engine = TaskPlanningEngine()
    plan = engine.plan("build a website", organization_id=1, task_id="t1")
    binding = bind_plan_context(plan, PlanContext(organization_id=1))
    assessment = assess_plan_risk(plan)
    first = build_approval_package(plan, binding, assessment)
    second = build_approval_package(plan, binding, assessment)
    assert first.package_hash == second.package_hash
    assert first.plan_hash == plan.plan_hash
    assert first.context_fingerprint == binding["context_fingerprint"]


def test_approval_package_fails_cross_tenant():
    engine = TaskPlanningEngine()
    plan = engine.plan("send an update", organization_id=1)
    binding = bind_plan_context(plan, PlanContext(organization_id=1))
    assessment = assess_plan_risk(plan)
    bad = dict(binding, organization_id=2)
    try:
        build_approval_package(plan, bad, assessment)
    except ValueError as exc:
        assert str(exc) == "tenant_context_mismatch"
    else:
        raise AssertionError("cross-tenant approval package must fail")
