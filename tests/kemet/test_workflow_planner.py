from app.automation.workflow_planner import build_steps, summarize_steps


def test_workflow_planner_builds_governed_sequential_step():
    steps = build_steps("business_insights", {"organization_id": 7})

    assert len(steps) == 1
    assert steps[0]["action"] == "business_insights"
    assert steps[0]["risk"] == "low"
    assert steps[0]["requires_approval"] is False
    assert steps[0]["on_failure"] == "stop"


def test_workflow_planner_marks_approval_checkpoint():
    steps = build_steps("refund_request")
    summary = summarize_steps(steps)

    assert steps[0]["requires_approval"] is True
    assert steps[0]["risk"] == "high"
    assert summary["approval_steps"] == 1
    assert summary["execution_mode"] == "governed_sequential"


def test_orchestrator_exposes_workflow_graph():
    from app.automation.orchestrator import orchestrator

    plan = orchestrator.plan("Analyze my business performance")

    assert plan["workflow"]["step_count"] == 1
    assert plan["steps"][0]["action"] == "business_insights"
