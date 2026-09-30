from app.core.plan_risk import assess_plan_risk
from app.core.task_planner import TaskPlanningEngine


def test_safe_plan_is_low_risk():
    plan = TaskPlanningEngine().plan("analyze sales", organization_id=1)
    assessment = assess_plan_risk(plan)
    assert assessment.level == "low"
    assert not assessment.external_side_effects
    assert not assessment.database_mutation
    assert not assessment.approval_required


def test_automation_plan_requires_approval():
    plan = TaskPlanningEngine().plan("automate sending invoices", organization_id=1)
    assessment = assess_plan_risk(plan)
    assert assessment.approval_required
    assert assessment.score >= 30
    assert assessment.assessment_hash


def test_assessment_is_deterministic():
    engine = TaskPlanningEngine()
    first = assess_plan_risk(engine.plan("build a website bot", organization_id=2, task_id="x"))
    second = assess_plan_risk(engine.plan("build a website bot", organization_id=2, task_id="x"))
    assert first.assessment_hash == second.assessment_hash
