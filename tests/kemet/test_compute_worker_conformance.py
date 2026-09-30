import hashlib
import json

from app.services.remote_worker_contract import build_request, sign_request, validate_response


def _job():
    payload = {"organization_id": 11, "shot_id": "worker-conformance-001", "canonical_shot_digest": "canonical-shot-11"}
    payload["digest"] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return payload


def _approval():
    return {"approved": True, "approver_id": "human-11", "authorization_id": "auth-11", "execution_gate": {"allowed": True, "plan_hash": "plan-11", "handoff_hash": "handoff-11"}}


def test_reference_worker_conforms_without_fake_render(monkeypatch):
    monkeypatch.setenv("KEMET_WORKER_SECRET", "worker-test-secret")
    from tools.compute_worker_reference.worker import app
    request_payload = build_request(organization_id=11, worker_id="reference-worker", job=_job(), approval=_approval())
    signature = sign_request(request_payload, "worker-test-secret")
    client = app.test_client()
    response = client.post("/v1/jobs", json=request_payload, headers={"X-Kemet-Worker-Signature": signature})
    assert response.status_code == 200
    body = response.get_json()
    validated = validate_response(response=body, request=request_payload, signature=response.headers["X-Kemet-Worker-Signature"], secret="worker-test-secret")
    assert validated["status"] == "REJECTED"
    assert validated["error"] == "reference_worker_has_no_renderer"
    assert validated["organization_id"] == 11
    assert validated["canonical_shot_digest"] == "canonical-shot-11"
    assert validated["provenance"]["trust"] == "untrusted"


def test_reference_worker_rejects_bad_signature(monkeypatch):
    monkeypatch.setenv("KEMET_WORKER_SECRET", "worker-test-secret")
    from tools.compute_worker_reference.worker import app
    request_payload = build_request(organization_id=11, worker_id="reference-worker", job=_job(), approval=_approval())
    client = app.test_client()
    response = client.post("/v1/jobs", json=request_payload, headers={"X-Kemet-Worker-Signature": "bad"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "worker_request_signature_invalid"
