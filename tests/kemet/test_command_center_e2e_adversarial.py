import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from wsgi import application



def _client_as_admin():
    application.config["WTF_CSRF_ENABLED"] = False
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "1"
        session["_fresh"] = True
    return client


def _plan(client, command="build a website"):
    response = client.post("/command-center/api/bos/plan", json={"command": command})
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["executed"] is False
    assert body["database_mutation"] is False
    assert body["external_call"] is False
    for step in body["task_plan"]["steps"]:
        assert isinstance(step["capabilities"], list)
        assert isinstance(step["depends_on"], list)
    return body


def test_e2e_plan_to_decide_rejects_tenant_tampering(monkeypatch):
    client = _client_as_admin()
    planned = _plan(client)
    payload = {
        "command": "build a website",
        "task_id": planned["task_id"],
        "approval_package_hash": planned["approval_package"]["package_hash"],
        "approved": False,
        "organization_id": 2,
    }
    from app.routes import command_center
    monkeypatch.setattr(command_center, "_organization_id", lambda: 2)
    response = client.post("/command-center/api/bos/decide-plan", json=payload)
    body = response.get_json()
    assert response.status_code == 409
    assert body["error"] == "approval_package_mismatch"
    assert body["executed"] is False


def test_e2e_plan_to_decide_rejects_route_tampering(monkeypatch):
    client = _client_as_admin()
    planned = _plan(client)
    from app.routes import command_center
    original = command_center.federation_routing_preview.preview

    def tampered(*args, **kwargs):
        routing = original(*args, **kwargs)
        data = routing.as_dict()
        data["provider"] = {"provider_id": "tampered-provider", "model_id": "tampered-model"}
        return copy.copy(routing).__class__(**{**routing.__dict__, "provider": data["provider"]})

    monkeypatch.setattr(command_center.federation_routing_preview, "preview", tampered)
    response = client.post("/command-center/api/bos/decide-plan", json={
        "command": "build a website",
        "task_id": planned["task_id"],
        "approval_package_hash": planned["approval_package"]["package_hash"],
        "approved": False,
    })
    body = response.get_json()
    assert response.status_code == 409
    assert body["error"] == "approval_package_mismatch"
    assert body["executed"] is False


def test_e2e_plan_to_decide_rejects_artifact_tampering():
    client = _client_as_admin()
    artifacts = [{"path": "tests/kemet/e2e_probe.txt", "content": "safe"}]
    planned = client.post("/command-center/api/bos/plan", json={
        "command": "build a website", "artifacts": artifacts
    })
    assert planned.status_code == 200, planned.get_json()
    body = planned.get_json()
    tampered = [{"path": "tests/kemet/e2e_probe.txt", "content": "tampered"}]
    response = client.post("/command-center/api/bos/decide-plan", json={
        "command": "build a website",
        "task_id": body["task_id"],
        "approval_package_hash": body["approval_package"]["package_hash"],
        "approved": False,
        "artifacts": tampered,
    })
    result = response.get_json()
    assert response.status_code == 409
    assert result["error"] == "approval_package_mismatch"
    assert result["executed"] is False


def test_e2e_decide_requires_binding_before_approval_side_effect():
    client = _client_as_admin()
    response = client.post("/command-center/api/bos/decide-plan", json={
        "command": "build a website",
        "task_id": "missing-binding",
        "approved": True,
    })
    body = response.get_json()
    assert response.status_code == 400
    assert body["error"] == "approval_binding_required"
    assert body["executed"] is False
