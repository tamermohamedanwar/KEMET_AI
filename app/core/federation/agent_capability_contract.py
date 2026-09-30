from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


AGENT_KINDS = frozenset({
    "conversation", "reasoning", "research", "planning", "analysis", "creation",
    "multimedia", "education", "business", "integration", "governance",
    "knowledge", "optimization", "monitoring", "execution_specialist",
})

AUTHORITY_LEVELS = frozenset({"advisory", "governed_submission", "canonical_executor"})


@dataclass(frozen=True)
class AgentCapabilityContract:
    """Provider-neutral capability contract for agents participating in Kemet."""

    contract_version: str
    agent_id: str
    provider_id: str
    kind: str
    capabilities: frozenset[str] = frozenset()
    authority: str = "advisory"
    execution_authority: bool = False
    requires_verification: bool = True
    requires_human_approval: bool = True
    supports_async: bool = False
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.agent_id or not self.provider_id:
            raise ValueError("agent_identity_required")
        if self.kind not in AGENT_KINDS:
            raise ValueError("unsupported_agent_kind")
        if self.authority not in AUTHORITY_LEVELS:
            raise ValueError("unsupported_agent_authority")
        if self.execution_authority and self.provider_id != "kemet":
            raise ValueError("external_agent_execution_authority_forbidden")
        if self.execution_authority and self.authority != "canonical_executor":
            raise ValueError("execution_authority_requires_canonical_executor")
        if self.authority == "canonical_executor" and self.provider_id != "kemet":
            raise ValueError("canonical_executor_must_be_kemet")

    def supports(self, required: set[str] | tuple[str, ...] | frozenset[str]) -> bool:
        return set(required).issubset(self.capabilities)

    def can_submit(self) -> bool:
        return self.authority in {"governed_submission", "canonical_executor"}

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_version": self.contract_version,
            "agent_id": self.agent_id,
            "provider_id": self.provider_id,
            "kind": self.kind,
            "capabilities": sorted(self.capabilities),
            "authority": self.authority,
            "execution_authority": self.execution_authority,
            "requires_verification": self.requires_verification,
            "requires_human_approval": self.requires_human_approval,
            "supports_async": self.supports_async,
            "metadata": dict(self.metadata),
        }
