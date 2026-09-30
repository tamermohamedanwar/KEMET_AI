"""Governed discovery and attestation for free remote Compute Fabric workers.

Discovery is read-only before admission and reuses the canonical worker registry,
contract and health-attestation boundaries. It never creates execution authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from typing import Any, Mapping
from urllib.parse import urlparse

from .free_compute_fabric import FreeComputeFabricV1
from .remote_worker_contract import validate_worker_url
from .remote_worker_registry import remote_worker_registry


class FreeWorkerDiscoveryService:
    VERSION = "1.1"
    SCHEMA = "kemet.media.free_worker_discovery.v1"
    CANDIDATES_ENV = "KEMET_FREE_WORKER_CANDIDATES"
    REQUIRED_CAPABILITY = "VIDEO_GENERATION"

    def discover(self, *, candidates: list[Mapping[str, Any]], now: int | None = None) -> dict[str, Any]:
        results = [self._probe(candidate, now=now) for candidate in candidates]
        ready = [item for item in results if item.get("ready") is True]
        snapshot_now = datetime.fromtimestamp(now, timezone.utc) if now is not None else None
        snapshot = FreeComputeFabricV1().snapshot([item["provider"] for item in ready], now=snapshot_now)
        payload = {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "candidate_count": len(results),
            "ready_count": len(ready),
            "results": results,
            "free_compute": snapshot,
            "status": "FREE_CAPACITY_READY" if ready else "WAITING_FOR_FREE_CAPACITY",
            "governance": {"execution_authority": False, "external_execution": False, "mcp": False},
        }
        payload["digest"] = self._digest(payload)
        return payload

    def discover_from_environment(self, *, now: int | None = None) -> dict[str, Any]:
        raw = os.getenv(self.CANDIDATES_ENV, "").strip()
        if not raw:
            url = os.getenv("KEMET_WAN_WORKER_URL", "").strip()
            if not url:
                return self.discover(candidates=[], now=now)
            candidates = [{"worker_id": "wan2_2_worker", "provider_id": "wan2_2_remote",
                           "endpoint": url, "capabilities": [self.REQUIRED_CAPABILITY], "free": True}]
        else:
            try:
                candidates = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError("free_worker_candidates_json_invalid") from exc
            if not isinstance(candidates, list):
                raise ValueError("free_worker_candidates_must_be_list")
        return self.discover(candidates=candidates, now=now)

    def _probe(self, candidate: Mapping[str, Any], *, now: int | None) -> dict[str, Any]:
        worker_id = str(candidate.get("worker_id") or "")
        provider_id = str(candidate.get("provider_id") or "")
        endpoint = str(candidate.get("endpoint") or "")
        try:
            if candidate.get("free") is not True:
                raise ValueError("free_candidate_required")
            if self.REQUIRED_CAPABILITY not in {str(x) for x in (candidate.get("capabilities") or [])}:
                raise ValueError("video_capability_required")
            endpoint = validate_worker_url(endpoint)
            parsed = urlparse(endpoint)
            if not parsed.hostname:
                raise ValueError("worker_hostname_required")
            if not worker_id or not provider_id:
                raise ValueError("worker_identity_required")
            snapshot = remote_worker_registry.register(
                worker_id=worker_id, provider_id=provider_id,
                capabilities=[str(x) for x in (candidate.get("capabilities") or [])],
                endpoint=endpoint, configured=True,
            )
            attested = remote_worker_registry.attest(snapshot=snapshot, now=now)
            attestation = dict(attested.get("attestation") or {})
            checks = dict(attestation.get("checks") or {})
            license_ok = self._license_ok(candidate, attestation)
            ready = bool(attested.get("healthy") and attested.get("available") and
                         attestation.get("ready") and license_ok)
            provider = remote_worker_registry.as_router_provider(attested)
            provider.update({
                "free": True, "status": "READY" if ready else "BLOCKED",
                "license_ok": license_ok,
                "capacity_evidence": {
                    "observed_at": attestation.get("observed_at"),
                    "attestation_digest": attestation.get("digest"),
                    "attestation": {"ready": bool(attestation.get("ready"))},
                    "hardware": attestation.get("hardware") or {},
                },
            })
            return {"worker_id": worker_id, "provider_id": provider_id, "endpoint": endpoint,
                    "ready": ready, "license_ok": license_ok, "checks": checks,
                    "attestation": attestation, "provider": provider}
        except Exception as exc:
            return {"worker_id": worker_id, "provider_id": provider_id, "endpoint": endpoint,
                    "ready": False, "license_ok": False, "error": type(exc).__name__,
                    "reason": str(exc)}

    @staticmethod
    def _license_ok(candidate: Mapping[str, Any], attestation: Mapping[str, Any]) -> bool:
        declared = candidate.get("license") or {}
        observed = attestation.get("license") or {}
        evidence = observed if isinstance(observed, Mapping) and observed else declared
        return bool(isinstance(evidence, Mapping) and evidence.get("commercial_use") is True)

    @staticmethod
    def _digest(payload: Mapping[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), default=str).encode()
        return sha256(raw).hexdigest()


free_worker_discovery_service = FreeWorkerDiscoveryService()
