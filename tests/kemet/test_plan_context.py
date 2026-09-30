import pytest

from app.core.plan_context import PlanContext, bind_plan_context
from app.core.task_planner import TaskPlanningEngine


def test_context_fingerprint_is_deterministic():
    a = PlanContext(1, 7, ("openai",), ("gpt-5.6",), "2")
    b = PlanContext(1, 7, ("openai",), ("gpt-5.6",), "2")
    assert a.fingerprint() == b.fingerprint()


def test_context_binds_same_tenant():
    plan = TaskPlanningEngine().plan("analyze sales", organization_id=1)
    bound = bind_plan_context(plan, PlanContext(1, 7))
    assert bound["plan_hash"] == plan.plan_hash
    assert bound["organization_id"] == 1


def test_context_rejects_cross_tenant_binding():
    plan = TaskPlanningEngine().plan("analyze sales", organization_id=1)
    with pytest.raises(ValueError, match="tenant_context_mismatch"):
        bind_plan_context(plan, PlanContext(2, 7))
