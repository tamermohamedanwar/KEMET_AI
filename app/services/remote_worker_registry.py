"""Registry for governed remote Compute Fabric workers."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from app.core.media.provider_adapter_contract import MediaProviderAdapterDescriptor
from .worker_health_attestation import worker_health_attestation


class RemoteWorkerRegistry:
    VERSION = "1.0"
    SCHEMA = "kemet.media.remote_worker_registry.v1"

    def register(self, *, worker_id: str, provider_id: str, capabilities: list[str], endpoint: str, configured: bool, healthy: bool = False, available: bool = False, capacity: Mapping[str, Any] | None = None) -> dict[str, Any]:
        descriptor = MediaProviderAdapterDescriptor(provider_id=provider_id, capabilities=tuple(capabilities))
        if not endpoint:
            raise ValueError("worker_endpoint_required")
        return self._snapshot(worker_id, endpoint, descriptor.snapshot(), configured, healthy, available, capacity or {})

    def _snapshot(self, worker_id: str, endpoint: str, descriptor: Mapping[str, Any], configured: bool, healthy: bool, available: bool, capacity: Mapping[str, Any]) -> dict[str, Any]:
        if not worker_id.strip():
            raise ValueError("worker_id_required")
        payload = {
            "schema": self.SCHEMA, "version": 1, "worker_id": worker_id,
            "endpoint": endpoint.rstrip("/"), "provider_id": descriptor["provider_id"],
            "capabilities": list(descriptor["capabilities"]), "configured": bool(configured),
            "healthy": bool(healthy), "available": bool(available), "capacity": dict(capacity),
            "trust": "untrusted", "execution_authority": False, "external_execution": False, "mcp": False,
        }
        payload["digest"] = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
        return payload

    def attest(self, *, snapshot: Mapping[str, Any], now: int | None = None) -> dict[str, Any]:
        attestation = worker_health_attestation.attest(
            worker_id=str(snapshot["worker_id"]), provider_id=str(snapshot["provider_id"]),
            endpoint=str(snapshot["endpoint"]), expected_capabilities=list(snapshot.get("capabilities") or []), now=now,
        )
        refreshed = self._snapshot(
            str(snapshot["worker_id"]), str(snapshot["endpoint"]),
            {"provider_id": snapshot["provider_id"], "capabilities": snapshot.get("capabilities") or [],
             "trust": "untrusted", "execution_authority": False, "external_execution": False, "mcp": False},
            bool(snapshot.get("configured")), attestation["ready"], attestation["ready"], attestation.get("capacity") or {},
        )
        refreshed["attestation"] = attestation
        return refreshed

    @staticmethod
    def as_router_provider(snapshot: Mapping[str, Any]) -> dict[str, Any]:
        return {"provider_id": snapshot["provider_id"], "model": snapshot.get("provider_id"), "capabilities": list(snapshot.get("capabilities") or []), "configured": bool(snapshot.get("configured")), "healthy": bool(snapshot.get("healthy")), "available": bool(snapshot.get("available")), "capacity": dict(snapshot.get("capacity") or {}), "features": list(snapshot.get("features") or [])}


remote_worker_registry = RemoteWorkerRegistry()
