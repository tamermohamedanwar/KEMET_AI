from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.core.ai_federation import AIFederationRegistry, ProviderProfile, ai_federation
from app.core.federation_policy import FederationPolicy
from app.core.model_intelligence import ModelIntelligenceRegistry, model_intelligence
from app.core.provider_health import ProviderHealthRegistry, provider_health
from app.core.provider_resilience import provider_resilience


@dataclass(frozen=True)
class RoutingDecision:
    provider_id: str
    reason: str
    required_capabilities: tuple[str, ...]
    primary: bool
    priority: int
    model_id: str | None = None
    model_reason: str = "provider_default"


class ProviderRouter:
    VERSION = "1.3"

    def __init__(self, registry: AIFederationRegistry | None = None, health: ProviderHealthRegistry | None = None,
                 models: ModelIntelligenceRegistry | None = None):
        self.registry = registry or ai_federation
        self.health = health or provider_health
        self.models = models or model_intelligence

    def decide(self, required_capabilities: Iterable[str] = (), *, preferred: str | None = None,
               require_configured: bool = False, policy: FederationPolicy | None = None,
               model: str | None = None) -> RoutingDecision:
        required_set = set(required_capabilities)
        if policy:
            required_set.update(policy.required_capabilities)
            preferred = preferred or policy.preferred_provider
            model = model or policy.default_model
        required = tuple(sorted(required_set))
        candidates = [p for p in self.registry.all()
                      if p.enabled and p.execution_ready and p.supports(required)
                      and self.health.is_healthy(p.provider_id)
                      and provider_resilience.available(p.provider_id)
                      and (not require_configured or p.is_configured())
                      and (not policy or policy.provider_allowed(p.provider_id))]
        if not candidates:
            raise LookupError("No healthy configured provider satisfies the requested capabilities")
        if preferred:
            preferred_profile = self.registry.get(preferred)
            if preferred_profile in candidates and preferred_profile.execution_ready:
                return self._decision(preferred_profile, "explicit_preference", required, policy, model)
        selected = candidates[0]
        return self._decision(selected, "capability_priority", required, policy, model)

    def _decision(self, profile: ProviderProfile, reason: str, required: tuple[str, ...],
                  policy: FederationPolicy | None, model: str | None) -> RoutingDecision:
        allowed_models = policy.allowed_models if policy else None
        if model:
            selected = self.models.get(profile.provider_id, model)
            if selected is None or not selected.supports(required) or (allowed_models is not None and model not in allowed_models):
                raise LookupError("Requested model is not available for the selected provider or policy")
            return RoutingDecision(profile.provider_id, reason, required, profile.primary, profile.priority,
                                   model, "explicit_or_policy_model")
        models = [item for item in self.models.for_provider(profile.provider_id)
                  if item.supports(required) and (allowed_models is None or item.model_id in allowed_models)]
        if models:
            selected = models[0]
            return RoutingDecision(profile.provider_id, reason, required, profile.primary, profile.priority,
                                   selected.model_id, "capability_model_priority")
        return RoutingDecision(profile.provider_id, reason, required, profile.primary, profile.priority)
