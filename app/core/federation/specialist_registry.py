from __future__ import annotations

from dataclasses import dataclass

from app.core.federation.agent_capability_contract import AgentCapabilityContract
from app.core.federation.manus_adapter import ManusAdapter
from app.core.federation.meta_adapter import MetaLlamaAdapter
from app.core.federation.specialist_contracts import SpecialistAdapter


@dataclass(frozen=True)
class SpecialistProfile:
    provider_id: str
    execution_kind: str
    capabilities: frozenset[str]
    verified_required: bool = True
    agent_kind: str = "reasoning"
    authority: str = "advisory"
    execution_authority: bool = False
    requires_human_approval: bool = True
    supports_async: bool = False
    agent_id: str = ""

    def capability_contract(self) -> AgentCapabilityContract:
        return AgentCapabilityContract(
            contract_version="1.0",
            agent_id=self.agent_id or f"{self.provider_id}.specialist",
            provider_id=self.provider_id,
            kind=self.agent_kind,
            capabilities=self.capabilities,
            authority=self.authority,
            execution_authority=self.execution_authority,
            requires_verification=self.verified_required,
            requires_human_approval=self.requires_human_approval,
            supports_async=self.supports_async,
            metadata={"execution_kind": self.execution_kind},
        )


class SpecialistRegistry:
    VERSION = "2.0"

    def __init__(self) -> None:
        self._adapters: dict[str, SpecialistAdapter] = {
            "manus": ManusAdapter(),
            "meta": MetaLlamaAdapter(),
        }
        self._profiles: dict[str, SpecialistProfile] = {
            "manus": SpecialistProfile(
                provider_id="manus", execution_kind="agent",
                capabilities=ManusAdapter.capabilities, agent_kind="research",
                authority="governed_submission", supports_async=True,
                agent_id="manus.research",
            ),
            "meta": SpecialistProfile(
                provider_id="meta", execution_kind="model",
                capabilities=MetaLlamaAdapter.capabilities, agent_kind="reasoning",
                authority="advisory", agent_id="meta.reasoning",
            ),
        }

    def get(self, provider_id: str) -> SpecialistAdapter | None:
        return self._adapters.get(provider_id)

    def profile(self, provider_id: str) -> SpecialistProfile | None:
        return self._profiles.get(provider_id)

    def capability_contract(self, provider_id: str) -> AgentCapabilityContract | None:
        profile = self.profile(provider_id)
        return profile.capability_contract() if profile else None

    def all(self) -> tuple[SpecialistProfile, ...]:
        return tuple(self._profiles[provider_id] for provider_id in sorted(self._profiles))

    def verified_candidates(self, required: set[str], verified_provider_ids: set[str]) -> tuple[SpecialistProfile, ...]:
        return tuple(
            profile for profile in self.all()
            if profile.verified_required
            and profile.provider_id in verified_provider_ids
            and required.issubset(profile.capabilities)
        )


specialist_registry = SpecialistRegistry()
