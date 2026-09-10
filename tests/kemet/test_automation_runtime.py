from app.core.automation_control_plane import AutomationPlan, AutomationStep
from app.core.automation_runtime import AutomationRuntime


def _plan(action="business_insights", *, dry_run=False, approval=False, risk="low"):
    return AutomationPlan(
        plan_id="runtime-test",
        organization_id=1,
        trigger="manual",
        dry_run=dry_run,
        approval_policy="human" if approval else "auto_safe",
        steps=(AutomationStep(
            step_id="step-1",
            action=action,
            parameters={"organization_id": 1},
            risk=risk,
            requires_approval=approval,
            reversible=not approval,
        ),),
    )


def test_simulation_never_executes(monkeypatch):
    runtime = AutomationRuntime()
    called = {"value": False}

    def fake_execute(*args, **kwargs):
        called["value"] = True
        return {"success": True}

    monkeypatch.setattr("app.core.automation_runtime.action_registry.execute", fake_execute)
    result = runtime.simulate(_plan(dry_run=True))
    assert result["success"] is True
    assert result["mode"] == "simulation"
    assert called["value"] is False


def test_side_effecting_plan_is_blocked_without_authorization():
    runtime = AutomationRuntime()
    plan = _plan("send_notification", dry_run=False, approval=True, risk="high")
    result = runtime.execute(plan)
    assert result["status"] == "blocked"
    assert result["gate"]["error"] == "execution_authorization_required"


def test_safe_execution_produces_receipt_and_is_idempotent(monkeypatch):
    runtime = AutomationRuntime()
    calls = {"value": 0}

    def fake_execute(*args, **kwargs):
        calls["value"] += 1
        return {"success": True, "status": "completed", "result": "ok"}

    monkeypatch.setattr("app.core.automation_runtime.action_registry.execute", fake_execute)
    plan = _plan()
    first = runtime.execute(plan)
    second = runtime.execute(plan)

    assert first["status"] == "completed"
    assert first["executed"] is True
    assert first["receipt"]["status"] == "completed"
    assert len(first["receipt"]["steps"]) == 1
    assert second["status"] == "idempotent_replay_blocked"
    assert second["executed"] is False
    assert calls["value"] == 1


def test_recurring_workflow_allows_distinct_execution_keys(monkeypatch):
    runtime = AutomationRuntime()
    calls = {"value": 0}

    def fake_execute(*args, **kwargs):
        calls["value"] += 1
        return {"success": True, "status": "completed"}

    monkeypatch.setattr("app.core.automation_runtime.action_registry.execute", fake_execute)
    plan = _plan()
    first = runtime.execute(plan, execution_key="schedule-job-1")
    second = runtime.execute(plan, execution_key="schedule-job-2")
    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert calls["value"] == 2
