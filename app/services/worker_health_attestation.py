"""Governed health, capacity, hardware and commercial-use attestation for remote workers."""
from __future__ import annotations

from hashlib import sha256
import json
import time
from typing import Any, Mapping
from urllib.parse import urlparse

from app.core.governed_http import governed_request


class WorkerHealthAttestation:
    VERSION = "1.2"
    SCHEMA = "kemet.media.worker_health_attestation.v1"
    REQUIRED_HARDWARE_EVIDENCE = ("gpu", "vram_mb", "compute_runtime")
    MAX_AGE_SECONDS = 60

    def attest(self, *, worker_id: str, provider_id: str, endpoint: str,
               expected_capabilities: list[str], now: int | None = None) -> dict[str, Any]:
        if not worker_id or not provider_id or not endpoint:
            raise ValueError("worker_identity_required")
        parsed = urlparse(endpoint)
        host = str(parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme != "https" or not host:
            raise ValueError("worker_https_endpoint_required")
        response = governed_request("GET", endpoint.rstrip("/") + "/health",
                                    allow_hosts=[host], timeout=(5, 10))
        if int(response.status_code) != 200:
            raise ValueError("worker_health_http_error")
        body = response.json()
        current = int(now if now is not None else time.time())
        reported_at = int(body.get("reported_at", current))
        age = max(0, current - reported_at)
        capabilities = sorted({str(x) for x in (body.get("capabilities") or [])})
        expected = sorted({str(x) for x in expected_capabilities})
        capacity = dict(body.get("capacity") or {})
        hardware = dict(body.get("hardware") or {})
        pricing = dict(body.get("pricing") or {})
        license_evidence = dict(body.get("license") or {})
        identity_ok = body.get("worker_id") == worker_id and body.get("provider_id") == provider_id
        capability_ok = set(expected).issubset(set(capabilities))
        status_ok = body.get("status") == "READY"
        freshness_ok = age <= self.MAX_AGE_SECONDS
        capacity_ok = self._capacity_ok(capacity)
        hardware_ok = self._hardware_ok(hardware)
        attestation_ok = bool((capacity.get("attestation") or {}).get("ready") is True)
        free_ok = pricing.get("free") is True
        license_ok = license_evidence.get("commercial_use") is True
        ready = (identity_ok and capability_ok and status_ok and freshness_ok and
                 capacity_ok and hardware_ok and attestation_ok and free_ok and license_ok)
        payload = {
            "schema": self.SCHEMA, "version": 1, "worker_id": worker_id,
            "provider_id": provider_id, "endpoint": endpoint.rstrip("/"),
            "reported_at": reported_at, "observed_at": current, "age_seconds": age,
            "status": body.get("status"), "capabilities": capabilities,
            "capacity": capacity, "hardware": hardware, "pricing": pricing,
            "license": license_evidence,
            "checks": {
                "identity_ok": identity_ok, "capability_ok": capability_ok,
                "status_ok": status_ok, "freshness_ok": freshness_ok,
                "capacity_ok": capacity_ok, "hardware_ok": hardware_ok,
                "attestation_ok": attestation_ok, "free_ok": free_ok,
                "license_ok": license_ok,
            },
            "ready": ready, "trust": "untrusted", "execution_authority": False,
            "external_execution": False, "mcp": False,
        }
        payload["digest"] = sha256(json.dumps(payload, sort_keys=True,
                                              ensure_ascii=False, separators=(",", ":"),
                                              default=str).encode()).hexdigest()
        return payload

    @classmethod
    def _hardware_ok(cls, hardware: Mapping[str, Any]) -> bool:
        if not isinstance(hardware, Mapping):
            return False
        if not str(hardware.get("gpu", "")).strip():
            return False
        try:
            return int(hardware.get("vram_mb", 0)) > 0 and bool(str(hardware.get("compute_runtime", "")).strip())
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _capacity_ok(capacity: Mapping[str, Any]) -> bool:
        try:
            in_flight = int(capacity.get("in_flight", 0))
            max_concurrency = int(capacity.get("max_concurrency", 0))
            queue_depth = int(capacity.get("queue_depth", 0))
            max_queue_depth = int(capacity.get("max_queue_depth", 0))
            return max_concurrency > 0 and in_flight < max_concurrency and queue_depth <= max_queue_depth
        except (TypeError, ValueError):
            return False


worker_health_attestation = WorkerHealthAttestation()
