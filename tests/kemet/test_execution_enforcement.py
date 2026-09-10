import importlib


def _load_bridge(monkeypatch):
    import agent.chatgpt_bridge as bridge
    bridge = importlib.reload(bridge)
    return bridge


def _auth_headers(bridge):
    return {
        "Authorization": f"Bearer {bridge.TOKEN}",
        "Content-Type": "application/json",
    }


def test_execution_without_authorization_never_calls_subprocess(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    assert bridge.TOKEN

    called = {"value": False}

    def fake_run(*args, **kwargs):
        called["value"] = True
        raise AssertionError("subprocess must not be called")

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)

    client = bridge.app.test_client()

    response = client.post(
        "/execution/run",
        headers=_auth_headers(bridge),
        json={
            "plan": {"action": "health"},
            "action": "health",
        },
    )

    assert response.status_code == 403
    assert called["value"] is False
    assert response.get_json()["error"] == "execution_authorization_required"


def test_execution_command_allowlist_blocks_unknown_command(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    assert bridge.TOKEN

    called = {"value": False}

    def fake_run(*args, **kwargs):
        called["value"] = True
        raise AssertionError("subprocess must not be called")

    monkeypatch.setattr(bridge.subprocess, "run", fake_run)

    client = bridge.app.test_client()

    response = client.post(
        "/execution/run",
        headers=_auth_headers(bridge),
        json={
            "plan": {"action": "not_allowed"},
            "authorization": {"fake": True},
            "action": "not_allowed",
        },
    )

    assert response.status_code == 403
    assert called["value"] is False
    assert response.get_json()["error"] in {
        "execution_token_required",
        "execution_plan_mismatch",
        "execution_action_mismatch",
        "command_not_allowed",
    }


def test_execution_authorization_consume_blocks_replay(monkeypatch):
    bridge = _load_bridge(monkeypatch)

    from app.core.execution.execution_boundary import execution_boundary

    def fake_require(plan, authorization, action):
        return {
            "allowed": True,
            "status": "authorized",
        }

    monkeypatch.setattr(
        execution_boundary,
        "require",
        fake_require,
    )

    class FakeAuthorization:
        def __init__(self):
            self.calls = 0

        def consume(self, authorization):
            self.calls += 1
            return self.calls == 1

    fake_auth = FakeAuthorization()

    monkeypatch.setattr(
        "app.core.execution.authorization.execution_authorization.consume",
        fake_auth.consume,
    )

    calls = {"value": 0}

    from app.automation.action_registry import registry

    def fake_execute(*args, **kwargs):
        calls["value"] += 1
        return {
            "success": True,
            "status": "completed",
            "result": "KEMET_TEST_EXECUTION_OK",
        }

    monkeypatch.setattr(registry, "execute", fake_execute)

    client = bridge.app.test_client()

    payload = {
        "plan": {"action": "health"},
        "authorization": {
            "plan_id": "test-plan",
            "one_time": True,
        },
        "action": "health",
    }

    headers = _auth_headers(bridge)

    first = client.post(
        "/execution/run",
        headers=headers,
        json=payload,
    )

    second = client.post(
        "/execution/run",
        headers=headers,
        json=payload,
    )

    assert first.status_code == 200
    assert first.get_json()["ok"] is True

    assert second.status_code == 403
    assert second.get_json()["error"] == "execution_authorization_used"

    assert fake_auth.calls == 2
    assert calls["value"] == 1
