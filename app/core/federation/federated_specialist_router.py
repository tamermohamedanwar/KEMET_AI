from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.core.ai_federation import AIFederationRegistry, ai_federation
from app.core.federation_policy import FederationPolicy
from app.core.provider_health import ProviderHealthRegistry, provider_health
from app.core.federation.specialist_registry import SpecialistRegistry, specialist_registry


@dataclass(frozen=True)
class SpecialistRoutingDecision:
    provider_id: str
    execution_kind: str
    capabilities: tuple[str, ...]
    reason: str
    requires_verified_connection: bool = True
    authority: str = "advisory"
    approval_required: bool = True
    policy_requirements: tuple[str, ...] = ()


class FederatedSpecialistRouter:
    VERSION = "2.0"

    def __init__(self, registry: AIFederationRegistry | None = None,
                 specialists: SpecialistRegistry | None = None,
                 health: ProviderHealthRegistry | None = None):
        self.registry = registry or ai_federation
        self.specialists = specialists or specialist_registry
        self.health = health or provider_health

    @staticmethod
    def _required(required_capabilities: Iterable[str], policy: FederationPolicy | None) -> set[str]:
        required = {str(item).strip() for item in required_capabilities if str(item).strip()}
        if policy:
            required.update(policy.required_capabilities)
        return required

    def decide(self, required_capabilities: Iterable[str], *, preferred: str | None = None,
               policy: FederationPolicy | None = None, verified: Iterable[str] = ()) -> SpecialistRoutingDecision:
        required = self._required(required_capabilities, policy)
        allowed = set(policy.allowed_providers) if policy and policy.allowed_providers else None
        verified_set = set(verified)
        candidates = []
        for profile in self.specialists.all():
            contract = profile.capability_contract()
            if not required.issubset(contract.capabilities):
                continue
            if allowed is not None and profile.provider_id not in allowed:
                continue
            if not self.health.is_healthy(profile.provider_id):
                continue
            if contract.requires_verification and profile.provider_id not in verified_set:
                continue
            candidates.append((profile, contract))
        if not candidates:
            raise LookupError("No verified specialist satisfies policy and requested capabilities")

        candidates.sort(key=lambda item: (
            item[0].provider_id != (preferred or (policy.preferred_provider if policy else None)),
            not item[1].can_submit(),
            item[0].provider_id,
        ))
        selected, contract = candidates[0]
        return SpecialistRoutingDecision(
            selected.provider_id,
            selected.execution_kind,
            tuple(sorted(required)),
            "capability_policy_match",
            contract.requires_verification,
            contract.authority,
            contract.requires_human_approval,
            tuple(sorted(policy.required_capabilities)) if policy else (),
        )
