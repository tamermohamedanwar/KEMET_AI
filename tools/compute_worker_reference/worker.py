"""Standalone reference Compute Fabric worker for contract conformance tests."""
from __future__ import annotations

from hashlib import sha256
import hmac, os, time
from flask import Flask, jsonify, request
from app.services.remote_worker_contract import RESPONSE_SCHEMA, canonical_digest

app = Flask(__name__)


def _secret() -> str:
    return os.getenv("KEMET_WORKER_SECRET", "")


def _verify_request(payload: dict, signature: str) -> None:
    secret = _secret()
    if not secret:
        raise ValueError("worker_secret_not_configured")
    expected = hmac.new(secret.encode(), canonical_digest(payload).encode(), sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise ValueError("worker_request_signature_invalid")
    if payload.get("schema") != "kemet.media.remote_worker_request.v1":
        raise ValueError("worker_request_schema_invalid")
    if int(payload.get("organization_id") or 0) <= 0:
        raise ValueError("organization_required")
    if payload.get("approval", {}).get("approved") is not True:
        raise ValueError("human_approval_required")
    if not payload.get("job", {}).get("canonical_shot_digest"):
        raise ValueError("canonical_shot_binding_required")


def _signed_response(body: dict):
    signature = hmac.new(_secret().encode(), canonical_digest(body).encode(), sha256).hexdigest()
    response = jsonify(body)
    response.headers["X-Kemet-Worker-Signature"] = signature
    return response


@app.get("/health")
def health():
    return jsonify({
        "status": "READY",
        "worker_id": os.getenv("KEMET_WORKER_ID", "reference-worker"),
        "provider_id": os.getenv("KEMET_WORKER_PROVIDER_ID", "reference"),
        "renderer": "REFERENCE_CONFORMANCE_ONLY",
        "reported_at": int(time.time()),
        "capabilities": ["VIDEO_GENERATION"],
        "capacity": {"in_flight": 0, "max_concurrency": 1, "queue_depth": 0, "max_queue_depth": 1},
    })


@app.post("/v1/jobs")
def jobs():
    try:
        payload = request.get_json(force=True, silent=False) or {}
        _verify_request(payload, request.headers.get("X-Kemet-Worker-Signature", ""))
        job = payload["job"]
        body = {
            "schema": RESPONSE_SCHEMA, "version": 1,
            "organization_id": int(payload["organization_id"]),
            "request_id": payload["request_id"], "idempotency_key": payload["idempotency_key"],
            "canonical_shot_digest": job["canonical_shot_digest"], "status": "REJECTED",
            "artifact": None,
            "provenance": {"source_type": "provider", "source_ref": "reference-worker", "trust": "untrusted", "digest": None},
            "worker": {"worker_id": payload["worker_id"], "provider_id": "reference", "received_at": int(time.time())},
            "error": "reference_worker_has_no_renderer",
            "governance": {"execution_authority": False, "external_execution": False, "mcp": False},
        }
        return _signed_response(body)
    except Exception as exc:
        return jsonify({"schema": RESPONSE_SCHEMA, "version": 1, "status": "REJECTED", "error": str(exc)}), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("KEMET_WORKER_PORT", "8790")))
