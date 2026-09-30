import uuid

from app.core.execution.runtime import canonical_execution_runtime
from app.core.federation.execution_envelope import execution_envelope


def _authorization():
    return {"plan_hash": "plan-1", "plan_id": "auth-1"}


def _envelope(key="exec-1", provider="kemet", action="business_insights"):
    return execution_envelope.build(
        approval_package_hash="pkg-1",
        decision_hash="dec-1",
        handoff_hash="handoff-1",
        authorization=_authorization(),
        execution_key=key,
        provider_id=provider,
        action=action,
    )


def _plan(**changes):
    plan = {
        "action": "business_insights",
        "parameters": {},
        "organization_id": 1,
        "execution_key": "exec-1",
        "provider_id": "kemet",
        "approval_package_hash": "pkg-1",
        "central_gate_handoff_hash": "handoff-1",
        "execution_envelope": _envelope(),
    }
    plan.update(changes)
    return plan


def _blocked_without_registry_call(monkeypatch, plan):
    calls = []
    monkeypatch.setattr(
        "app.core.execution.runtime.execution_boundary.require",
        lambda **kwargs: {"allowed": True},
    )

    class Registry:
        def execute(self, *args, **kwargs):
            calls.append(True)
            raise AssertionError("invalid envelope reached action registry")

    result = canonical_execution_runtime.execute(
        plan=plan,
        authorization=_authorization(),
        action_registry=Registry(),
        user_id=1,
    )
    assert result["success"] is False
    assert result["executed"] is False
    assert result["error"] == "execution_envelope_invalid"
    assert calls == []


def test_canonical_runtime_blocks_tampered_envelope(monkeypatch):
    env = _envelope()
    env["decision_hash"] = "tampered"
    _blocked_without_registry_call(monkeypatch, _plan(execution_envelope=env))


def test_canonical_runtime_blocks_provider_mismatch(monkeypatch):
    _blocked_without_registry_call(monkeypatch, _plan(provider_id="manus"))


def test_canonical_runtime_blocks_action_mismatch(monkeypatch):
    _blocked_without_registry_call(monkeypatch, _plan(action="refund_request"))


def test_canonical_runtime_blocks_execution_key_replay(monkeypatch):
    env = _envelope(key=uuid.uuid4().hex)
    _blocked_without_registry_call(monkeypatch, _plan(execution_key="different-key", execution_envelope=env))


def test_canonical_runtime_separates_execution_status_from_business_status(monkeypatch):
    monkeypatch.setattr(
        "app.core.execution.runtime.execution_boundary.require",
        lambda **kwargs: {"allowed": True},
    )
    monkeypatch.setattr(
        "app.core.execution.runtime.execution_authorization.consume",
        lambda authorization: True,
    )

    class Registry:
        def exists(self, action):
            return action == "check_order"

        def execute(self, action, parameters, user_id=None):
            return {"success": True, "status": "processing", "order_id": "E2E-STATUS"}

    result = canonical_execution_runtime.execute(
        plan={"action": "check_order", "parameters": {"order_id": "E2E-STATUS"}},
        authorization={"plan_hash": "plan-1"},
        action_registry=Registry(),
        user_id=1,
    )

    assert result["success"] is True
    assert result["executed"] is True
    assert result["execution_status"] == "completed"
    assert result["business_status"] == "processing"
    assert result["status"] == "processing"
