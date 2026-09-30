from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable

from app.core.ai_federation import ai_federation
from app.core.federation.provider_catalog import provider_catalog
from app.core.provider_health import provider_health

@dataclass(frozen=True)
class CapabilityEntry:
    capability: str
    providers: tuple[str, ...]
    ready_providers: tuple[str, ...]
    def as_dict(self) -> dict[str, Any]:
        return {"capability": self.capability, "providers": list(self.providers), "ready_providers": list(self.ready_providers)}

class CapabilityFederation:
    VERSION = "1.2"

    def _provider_state(self, provider_id: str) -> dict[str, Any]:
        profile = next((p for p in ai_federation.all() if p.provider_id == provider_id), None)
        if profile is None:
            return {"provider_id": provider_id, "known": False, "ready": False}
        return {
            "provider_id": provider_id,
            "known": True,
            "enabled": bool(profile.enabled),
            "execution_ready": bool(profile.execution_ready),
            "configured": bool(profile.is_configured()),
            "healthy": bool(provider_health.is_healthy(provider_id)),
            "priority": int(profile.priority),
        }

    def snapshot(self, *, configured_only: bool = False) -> dict[str, Any]:
        entries: dict[str, dict[str, list[str]]] = {}
        for item in provider_catalog.all():
            if configured_only and not item.configured: continue
            for capability in item.capabilities:
                bucket = entries.setdefault(capability, {"providers": [], "ready_providers": []})
                bucket["providers"].append(item.provider_id)
                if item.adapter_ready and item.execution_ready and provider_health.is_healthy(item.provider_id):
                    bucket["ready_providers"].append(item.provider_id)
        capabilities = [CapabilityEntry(k, tuple(sorted(v["providers"])), tuple(sorted(v["ready_providers"]))).as_dict() for k, v in sorted(entries.items())]
        payload = {"version": self.VERSION, "capabilities": capabilities}
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        payload["fingerprint"] = sha256(raw.encode("utf-8")).hexdigest()
        return payload

    def resolve(self, capability: str, *, configured_only: bool = True) -> dict[str, Any]:
        name = str(capability or "").strip()
        if not name: raise ValueError("capability_required")
        item = next((x for x in self.snapshot(configured_only=configured_only)["capabilities"] if x["capability"] == name), None)
        if not item: raise LookupError("capability_unavailable")
        return item

    def rank(self, required: Iterable[str], *, verified: set[str], preferred: str | None = None) -> list[dict[str, Any]]:
        required_set = {str(x).strip() for x in required if str(x).strip()}
        if not required_set: return []
        ranked = []
        for profile in ai_federation.all():
            if profile.provider_id not in verified or not profile.enabled or not profile.execution_ready: continue
            if not provider_health.is_healthy(profile.provider_id) or not profile.is_configured(): continue
            coverage = len(required_set.intersection(profile.capabilities))
            if coverage != len(required_set): continue
            score = coverage * 1000 + profile.priority + (10000 if preferred == profile.provider_id else 0)
            ranked.append({"provider_id": profile.provider_id, "display_name": profile.display_name, "score": score, "priority": profile.priority, "coverage": coverage, "required_capabilities": sorted(required_set)})
        return sorted(ranked, key=lambda item: (-item["score"], item["provider_id"]))

    def route(self, required: Iterable[str], *, verified: set[str], preferred: str | None = None) -> dict[str, Any]:
        required_list = [str(x).strip() for x in required if str(x).strip()]
        ranked = self.rank(required_list, verified=verified, preferred=preferred)
        return {"version": self.VERSION, "required_capabilities": sorted(set(required_list)), "selected": ranked[0] if ranked else None, "candidates": ranked[:8], "selection_policy": "capability_coverage_then_priority_then_preference", "provider_states": [self._provider_state(x["provider_id"]) for x in ranked[:8]]}

capability_federation = CapabilityFederation()
