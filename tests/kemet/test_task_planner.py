import pytest

from app.core.task_planner import TaskPlanningEngine


@pytest.fixture
def planner():
    return TaskPlanningEngine()


def test_planner_requires_tenant(planner):
    with pytest.raises(ValueError):
        planner.plan("build a website", organization_id=0)


def test_coding_task_decomposes_and_requires_review(planner):
    plan = planner.plan("build a website bot", organization_id=1, task_id="t1")
    assert plan.task_type == "coding"
    assert len(plan.steps) == 2
    assert plan.steps[0].step_id == "analyze"
    assert plan.steps[1].requires_approval
    assert plan.plan_hash


def test_automation_is_high_risk(planner):
    plan = planner.plan("automate sending invoices", organization_id=1)
    assert plan.task_type == "automation"
    assert plan.risk == "high"
    assert plan.requires_approval


def test_compile_is_simulation_only(planner):
    plan = planner.plan("research market comparison", organization_id=2)
    compiled = planner.compile(plan)
    assert compiled["simulation"] is True
    assert compiled["executed"] is False


def test_plan_hash_is_deterministic(planner):
    first = planner.plan("analyze sales", organization_id=4, task_id="same")
    second = planner.plan("analyze sales", organization_id=4, task_id="same")
    assert first.plan_hash == second.plan_hash


def test_federated_execution_binding_targets_review_step(planner):
    plan = planner.plan("build a website bot", organization_id=1, task_id="fed-1")
    bound = planner.bind_federated_execution(
        plan, provider_id="openrouter", model_id="openai/gpt-4o-mini"
    )
    assert bound.requires_approval
    assert bound.steps[0].action == "business_insights"
    assert bound.steps[-1].action == "federated_command"
    assert bound.steps[-1].parameters["provider_id"] == "openrouter"
    assert bound.steps[-1].parameters["model_id"] == "openai/gpt-4o-mini"
    assert bound.plan_hash != plan.plan_hash
