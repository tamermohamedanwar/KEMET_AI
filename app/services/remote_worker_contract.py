"""Provider-independent governed remote worker contract for Kemet Compute Fabric."""
from __future__ import annotations

from hashlib import sha256
import hmac, json, time, uuid
from typing import Any, Mapping
from urllib.parse import urlparse

SCHEMA = "kemet.media.remote_worker_contract.v1"
REQUEST_SCHEMA = "kemet.media.remote_worker_request.v1"
RESPONSE_SCHEMA = "kemet.media.remote_worker_response.v1"


def canonical_digest(value: Mapping[str, Any]) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
    return sha256(raw).hexdigest()


def build_request(*, organization_id: int, worker_id: str, job: Mapping[str, Any], approval: Mapping[str, Any]) -> dict[str, Any]:
    if int(organization_id or 0) <= 0:
        raise ValueError("organization_required")
    if not worker_id:
        raise ValueError("worker_id_required")
    if not job.get("digest") or not job.get("shot_id") or not job.get("canonical_shot_digest"):
        raise ValueError("canonical_job_binding_required")
    if approval.get("approved") is not True:
        raise ValueError("human_approval_required")
    gate = approval.get("execution_gate") or {}
    if gate.get("allowed") is not True:
        raise ValueError("execution_gate_required")
    request = {
        "schema": REQUEST_SCHEMA, "version": 1, "contract": SCHEMA,
        "request_id": str(uuid.uuid4()), "idempotency_key": str(job["digest"]),
        "organization_id": int(organization_id), "worker_id": str(worker_id),
        "job": dict(job),
        "approval": {"approved": True, "approver_id": approval.get("approver_id"), "authorization_id": approval.get("authorization_id"), "plan_hash": gate.get("plan_hash"), "handoff_hash": gate.get("handoff_hash")},
        "governance": {"human_approval_required": True, "execution_authority": False, "external_execution": False, "mcp": False},
        "issued_at": int(time.time()),
    }
    request["request_digest"] = canonical_digest(request)
    return request


def sign_request(request: Mapping[str, Any], secret: str) -> str:
    if not secret:
        raise ValueError("worker_secret_required")
    return hmac.new(secret.encode(), canonical_digest(request).encode(), sha256).hexdigest()


def validate_response(*, response: Mapping[str, Any], request: Mapping[str, Any], signature: str | None = None, secret: str | None = None) -> dict[str, Any]:
    if not isinstance(response, Mapping):
        raise ValueError("worker_response_mapping_required")
    data = dict(response)
    if data.get("schema") != RESPONSE_SCHEMA or data.get("version") != 1:
        raise ValueError("worker_response_schema_invalid")
    if int(data.get("organization_id") or 0) != int(request["organization_id"]):
        raise ValueError("worker_response_tenant_mismatch")
    if data.get("request_id") != request.get("request_id"):
        raise ValueError("worker_response_request_mismatch")
    if data.get("idempotency_key") != request.get("idempotency_key"):
        raise ValueError("worker_response_idempotency_mismatch")
    if data.get("canonical_shot_digest") != request["job"].get("canonical_shot_digest"):
        raise ValueError("worker_response_shot_mismatch")
    if data.get("status") not in {"COMPLETED", "FAILED", "REJECTED"}:
        raise ValueError("worker_response_status_invalid")
    if data.get("status") == "COMPLETED":
        artifact = data.get("artifact") or {}
        if not artifact.get("uri") or not artifact.get("sha256"):
            raise ValueError("worker_artifact_binding_required")
    if signature and secret:
        expected = hmac.new(secret.encode(), canonical_digest(data).encode(), sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("worker_response_signature_invalid")
    data["trust"] = "untrusted"
    data["execution_authority"] = False
    data["external_execution"] = False
    data["mcp"] = False
    return data


def validate_worker_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("worker_https_required")
    return url.rstrip("/")
