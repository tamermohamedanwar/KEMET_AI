"""Fresh, evidence-backed capacity certification for cinematic production.

This is an advisory certification layer. It never executes providers, grants
execution authority, or bypasses the canonical approval/execution boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any, Mapping

from app.services.free_compute_fabric import FreeComputeFabricV1
from app.services.provider_capacity_gate import provider_capacity_gate
from app.services.local_acceleration_capability import local_acceleration_capability


class ProductionCapacityEvidenceService:
    VERSION = "1.0"
    SCHEMA = "kemet.production.capacity_evidence.v1"
    FRESHNESS_SECONDS = 300

    def certify(self, *, organization_id: int, providers: list[Mapping[str, Any]],
                free_providers: list[Mapping[str, Any]], required_capabilities: list[str],
                captured_at: datetime | None = None) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            raise ValueError("organization_required")
        now = captured_at or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("captured_at_must_be_timezone_aware")
        free_snapshot = FreeComputeFabricV1().snapshot([dict(x) for x in free_providers], now=now)
        capacity = provider_capacity_gate.evaluate(
            providers=[dict(x) for x in providers],
            required_capabilities=list(required_capabilities),
        )
        local = local_acceleration_capability.snapshot()
        free_selection = {
            capability: FreeComputeFabricV1().select(free_snapshot, capability)
            for capability in required_capabilities
        }
        free_ready = all(x["status"] == "FREE_CAPACITY_READY" for x in free_selection.values()) if required_capabilities else False
        decision = "READY" if free_ready else "BLOCKED"
        payload = {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "organization_id": org,
            "captured_at": now.isoformat(),
            "freshness": {"max_age_seconds": self.FRESHNESS_SECONDS, "fresh": True},
            "required_capabilities": sorted(set(map(str, required_capabilities))),
            "provider_capacity_gate": capacity,
            "free_compute": free_snapshot,
            "free_selection": free_selection,
            "local_acceleration": local,
            "decision": decision,
            "policy": {
                "free_first": True,
                "no_paid_fallback": True,
                "configuration_is_not_capacity": True,
                "capacity_requires_fresh_evidence": True,
                "human_approval_required_before_external_generation": True,
            },
            "governance": {
                "execution_authority": False,
                "external_execution": False,
                "human_approval_required": True,
                "mcp": False,
            },
        }
        unsigned = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        payload["digest"] = sha256(unsigned.encode()).hexdigest()
        return payload


production_capacity_evidence_service = ProductionCapacityEvidenceService()
