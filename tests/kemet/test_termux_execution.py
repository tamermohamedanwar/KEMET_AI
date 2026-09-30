import importlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_task_planner_binds_governed_termux_operations():
    from app.core.task_planner import TaskPlanningEngine

    plan = TaskPlanningEngine().plan("compile the project", organization_id=1, task_id="termux-1")
    assert plan.requires_approval is True
    assert plan.steps[0].action == "termux_engineering"
    assert plan.steps[0].parameters["operation"] == "compile"


def test_task_planner_does_not_bind_arbitrary_shell():
    from app.core.task_planner import TaskPlanningEngine

    plan = TaskPlanningEngine().plan("build a website", organization_id=1, task_id="termux-2")
    assert all(step.action != "termux_engineering" for step in plan.steps)


def test_termux_service_rejects_unknown_operation():
    from app.core.execution.termux_execution import TermuxExecutionError, TermuxExecutionService

    service = TermuxExecutionService()
    try:
        service.execute(operation="rm_rf", plan={}, authorization={}, action="termux_engineering")
    except TermuxExecutionError as exc:
        assert str(exc) == "termux_operation_not_allowed"
    else:
        raise AssertionError("unknown Termux operation must fail closed")


def test_termux_service_uses_governed_bridge(monkeypatch):
    import app.core.execution.termux_execution as module

    service = module.TermuxExecutionService()
    monkeypatch.setattr(service, "token", "test-token")

    class Response:
        status_code = 200

        def json(self):
            return {"ok": True, "operation": "compile", "executed": True}

    calls = {}

    def fake_post(url, **kwargs):
        calls["url"] = url
        calls["json"] = kwargs["json"]
        return Response()

    monkeypatch.setattr(module.requests, "post", fake_post)
    result = service.execute(
        operation="compile",
        plan={"plan_id": "p1"},
        authorization={"plan_id": "p1"},
        action="termux_engineering",
    )
    assert result["executed"] is True
    assert calls["url"].endswith("/termux/run")
    assert calls["json"]["operation"] == "compile"


def test_termux_agent_governed_route_blocks_unknown_operation(monkeypatch):
    import agent.termux_agent as agent
    agent = importlib.reload(agent)
    client = agent.app.test_client()
    response = client.post(
        "/governed/run",
        headers={"Authorization": f"Bearer {agent.TOKEN}"},
        json={"operation": "rm_rf", "plan": {}, "authorization": {}, "action": "termux_engineering"},
    )
    assert response.status_code == 403
    assert response.get_json()["error"] == "termux_operation_not_allowed"


def test_termux_action_receives_operation_parameters(monkeypatch):
    from app.automation.action_registry import registry

    captured = {}

    def fake_execute(**kwargs):
        captured.update(kwargs)
        return {"ok": True, "operation": "compile", "executed": True}

    monkeypatch.setattr("app.core.execution.termux_execution.termux_execution.execute", fake_execute)
    result = registry.execute(
        "termux_engineering",
        {
            "operation": "compile",
            "_execution_plan": {"plan_id": "p1"},
            "_execution_authorization": {"plan_id": "p1"},
            "_execution_action": "termux_engineering",
        },
    )
    assert result["success"] is True
    assert captured["operation"] == "compile"


def test_termux_service_rejects_action_mismatch():
    from app.core.execution.termux_execution import TermuxExecutionError, TermuxExecutionService

    service = TermuxExecutionService()
    try:
        service.execute(operation="compile", plan={}, authorization={}, action="federated_command")
    except TermuxExecutionError as exc:
        assert str(exc) == "termux_action_binding_invalid"
    else:
        raise AssertionError("Termux operation must remain bound to its governed action")


def test_bridge_execution_preserves_termux_parameters(monkeypatch):
    import agent.chatgpt_bridge as bridge
    bridge = importlib.reload(bridge)
    from app.core.execution.execution_boundary import execution_boundary
    monkeypatch.setattr(execution_boundary, "require", lambda **kwargs: {"allowed": True})
    captured = {}

    def fake_execute(**kwargs):
        captured.update(kwargs)
        return {"success": True, "executed": True}

    from app.core.execution.runtime import canonical_execution_runtime
    monkeypatch.setattr(canonical_execution_runtime, "execute", fake_execute)
    client = bridge.app.test_client()
    response = client.post(
        "/execution/run",
        headers={"Authorization": f"Bearer {bridge.TOKEN}"},
        json={
            "plan": {"action": "termux_engineering", "command": "compile", "parameters": {"operation": "compile"}},
            "authorization": {"plan_id": "p1"},
            "action": "termux_engineering",
        },
    )
    assert response.status_code == 200
    assert captured["plan"]["parameters"]["operation"] == "compile"
