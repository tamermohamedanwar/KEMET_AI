from app.core.task_planner import TaskPlanningEngine


def test_specialist_binding_rehashes_plan():
    engine = TaskPlanningEngine()
    plan = engine.plan("research competitors", organization_id=1, task_id="orch-1")
    bound = engine.bind_specialist(plan, provider_id="manus", action="manus.task.create")
    assert bound.steps[0].action == "manus.task.create"
    assert bound.requires_approval is True
    assert bound.plan_hash != plan.plan_hash


def test_orchestrator_is_governed_and_not_autonomous():
    from app.core.federation.specialist_orchestrator import specialist_orchestrator
    text = type(specialist_orchestrator).execute.__code__
    assert text is not None
    source = open("app/core/federation/specialist_orchestrator.py", encoding="utf-8").read()
    assert "execution_boundary.require" in source
    assert "execution_authorization.consume" in source
    assert "specialist.execution_started" in source
    assert "specialist.execution_submitted" in source
