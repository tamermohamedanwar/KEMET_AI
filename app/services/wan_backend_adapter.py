"""Wan backend boundary through the governed remote Compute Fabric worker."""
from __future__ import annotations

import json, os
from typing import Any, Mapping

from app.core.governed_http import governed_request
from .remote_worker_contract import build_request, sign_request, validate_response, validate_worker_url
from .remote_worker_registry import remote_worker_registry


class WanBackendAdapter:
    VERSION = "2.0"
    PROVIDER_ID = "wan2_2_remote"
    WORKER_ID = "wan2_2_worker"
    SCHEMA = "kemet.media.backend_job.v1"
    MODEL_PROFILES = {
        "cinematic_t2v": {"model": "Wan2.2-T2V-A14B", "mode": "t2v", "capability": "VIDEO_GENERATION"},
        "cinematic_i2v": {"model": "Wan2.2-I2V-A14B", "mode": "i2v", "capability": "VIDEO_GENERATION"},
        "fast_ti2v": {"model": "Wan2.2-TI2V-5B", "mode": "ti2v", "capability": "VIDEO_GENERATION"},
        "character_animation": {"model": "Wan2.2-Animate-14B", "mode": "animate", "capability": "VIDEO_GENERATION"},
    }

    def preflight(self) -> dict[str, Any]:
        url = os.getenv("KEMET_WAN_WORKER_URL", "")
        snapshot = None
        if url:
            snapshot = remote_worker_registry.register(worker_id=self.WORKER_ID, provider_id=self.PROVIDER_ID, capabilities=["VIDEO_GENERATION"], endpoint=url, configured=True, healthy=False, available=False, capacity={"in_flight": 0, "max_concurrency": 1, "queue_depth": 0, "max_queue_depth": 4})
        return {
            "provider_id": self.PROVIDER_ID, "backend": "Wan 2.2",
            "worker_configured": bool(url), "local_model_installed": False,
            "transport": "governed_https_remote_worker", "status": "WAITING_FOR_WORKER_VERIFICATION" if url else "WAITING_FOR_REMOTE_WORKER",
            "worker_snapshot": snapshot, "execution_authority": False, "external_execution": False, "mcp": False,
        }

    def build_job(self, *, organization_id: int, shot: Mapping[str, Any], asset_gate: Mapping[str, Any], profile_id: str = "cinematic_i2v") -> dict[str, Any]:
        if profile_id not in self.MODEL_PROFILES:
            raise ValueError("wan_model_profile_invalid")
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        if asset_gate.get("status") != "BOUND":
            raise ValueError("asset_binding_gate_required")
        if not shot.get("shot_id") or not shot.get("canonical_shot_digest"):
            raise ValueError("canonical_shot_binding_required")
        payload = {
            "schema": self.SCHEMA, "version": 2, "provider_id": self.PROVIDER_ID,
            "model_family": "Wan 2.2", "organization_id": int(organization_id),
            "render_profile": dict(self.MODEL_PROFILES[profile_id]), "profile_id": profile_id,
            "shot_id": str(shot["shot_id"]), "canonical_shot_digest": str(shot["canonical_shot_digest"]),
            "inputs": {"reference_assets": asset_gate.get("references"), "conditioning": "canonical_shot"},
            "execution": {"remote_worker_required": True, "automatic": False, "approval_required": True, "external_execution": False},
        }
        from app.services.remote_worker_contract import canonical_digest
        payload["digest"] = canonical_digest(payload)
        return payload

    def execute(self, *, job: Mapping[str, Any], approval: Mapping[str, Any]) -> dict[str, Any]:
        if approval.get("approved") is not True:
            return {"status": "blocked", "error": "human_approval_required", "executed": False}
        if (approval.get("execution_gate") or {}).get("allowed") is not True:
            return {"status": "blocked", "error": "execution_gate_required", "executed": False}
        url = os.getenv("KEMET_WAN_WORKER_URL", "")
        secret = os.getenv("KEMET_WAN_WORKER_SECRET", "")
        if not url:
            return {"status": "blocked", "error": "wan_remote_worker_not_configured", "executed": False, "provider_id": self.PROVIDER_ID}
        if not secret:
            return {"status": "blocked", "error": "wan_remote_worker_secret_not_configured", "executed": False, "provider_id": self.PROVIDER_ID}
        try:
            endpoint = validate_worker_url(url) + "/v1/jobs"
            request = build_request(organization_id=int(job["organization_id"]), worker_id=self.WORKER_ID, job=job, approval=approval)
            signature = sign_request(request, secret)
            response = governed_request("POST", endpoint, allow_hosts=[urlparse_host(url)], headers={"Content-Type": "application/json", "X-Kemet-Worker-Signature": signature}, data=json.dumps(request, separators=(",", ":")), timeout=(5, 30))
            data = response.json()
            validated = validate_response(response=data, request=request, signature=response.headers.get("X-Kemet-Worker-Signature"), secret=secret)
            return {"status": "completed" if validated["status"] == "COMPLETED" else validated["status"].lower(), "executed": validated["status"] == "COMPLETED", "provider_id": self.PROVIDER_ID, "worker_id": self.WORKER_ID, "response": validated}
        except Exception as exc:
            return {"status": "blocked", "error": "remote_worker_request_failed", "detail": type(exc).__name__, "executed": False, "provider_id": self.PROVIDER_ID}


def urlparse_host(url: str) -> str:
    from urllib.parse import urlparse
    return str(urlparse(url).hostname or "").lower().rstrip(".")


wan_backend_adapter = WanBackendAdapter()
