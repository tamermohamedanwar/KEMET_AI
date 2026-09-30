from __future__ import annotations

from typing import Mapping

from app.core.ai_federation import ai_federation
from app.core.model_intelligence import model_intelligence
from app.core.provider_health import provider_health
from app.core.provider_usage_telemetry import provider_usage_telemetry
from app.core.federation_policy import federation_policy


class ProviderObservability:
    VERSION = "1.1"

    def snapshot(self, organization_id: int | None = None) -> Mapping[str, object]:
        health = {item["provider_id"]: dict(item) for item in provider_health.snapshot()}
        policy = federation_policy.for_organization(organization_id)
        providers = []
        for profile in ai_federation.all():
            item = {
                "provider_id": profile.provider_id,
                "display_name": profile.display_name,
                "enabled": profile.enabled,
                "primary": profile.primary,
                "priority": profile.priority,
                "configured": profile.is_configured(),
                "allowed_by_policy": policy.provider_allowed(profile.provider_id),
                "capabilities": sorted(profile.capabilities),
                "health": health.get(profile.provider_id, {
                    "provider_id": profile.provider_id, "healthy": True, "failures": 0,
                    "successes": 0, "cooldown_seconds": 0.0, "last_error_type": None,
                    "last_latency_ms": None,
                }),
                "models": [m for m in model_intelligence.snapshot() if m["provider_id"] == profile.provider_id],
                "usage": next((item for item in provider_usage_telemetry.snapshot() if item["provider_id"] == profile.provider_id), {"provider_id": profile.provider_id, "requests": 0, "successes": 0, "failures": 0, "cost_status": "not_observed"}),
            }
            providers.append(item)
        return {"version": self.VERSION, "providers": providers, "models": model_intelligence.snapshot(),
                "usage_telemetry_version": provider_usage_telemetry.VERSION,
                "policy": federation_policy.snapshot()}


provider_observability = ProviderObservability()
