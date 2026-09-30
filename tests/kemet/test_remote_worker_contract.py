import hashlib
import json

import pytest

from app.services.remote_worker_contract import build_request, sign_request, validate_response, validate_worker_url


def job():
    payload = {"organization_id": 7, "shot_id": "golden-001", "canonical_shot_digest": "shot-digest"}
    payload["digest"] = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return payload


def approval():
    return {"approved": True, "approver_id": "human-1", "authorization_id": "auth-1", "execution_gate": {"allowed": True, "plan_hash": "plan-hash", "handoff_hash": "handoff-hash"}}


def test_request_binds_tenant_shot_and_idempotency():
    request = build_request(organization_id=7, worker_id="wan2_2_worker", job=job(), approval=approval())
    assert request["organization_id"] == 7
    assert request["idempotency_key"] == job()["digest"]
    assert request["job"]["canonical_shot_digest"] == "shot-digest"
    assert request["governance"]["mcp"] is False


def test_request_requires_human_approval():
    with pytest.raises(ValueError, match="human_approval_required"):
        build_request(organization_id=7, worker_id="wan2_2_worker", job=job(), approval={"approved": False})


def test_response_requires_exact_tenant_and_shot_binding():
    request = build_request(organization_id=7, worker_id="wan2_2_worker", job=job(), approval=approval())
    response = {"schema": "kemet.media.remote_worker_response.v1", "version": 1, "organization_id": 7, "request_id": request["request_id"], "idempotency_key": request["idempotency_key"], "canonical_shot_digest": "shot-digest", "status": "COMPLETED", "artifact": {"uri": "https://worker.example/artifacts/a.mp4", "sha256": "artifact-digest"}}
    secret = "test-secret"
    response["_signature"] = None
    validated = validate_response(response=response, request=request)
    assert validated["trust"] == "untrusted"
    assert validated["execution_authority"] is False


def test_response_rejects_tenant_escape():
    request = build_request(organization_id=7, worker_id="wan2_2_worker", job=job(), approval=approval())
    response = {"schema": "kemet.media.remote_worker_response.v1", "version": 1, "organization_id": 8, "request_id": request["request_id"], "idempotency_key": request["idempotency_key"], "canonical_shot_digest": "shot-digest", "status": "COMPLETED", "artifact": {"uri": "https://worker.example/a.mp4", "sha256": "d"}}
    with pytest.raises(ValueError, match="tenant_mismatch"):
        validate_response(response=response, request=request)


def test_worker_url_requires_https():
    with pytest.raises(ValueError, match="https"):
        validate_worker_url("http://worker.example")
