from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class AgentTool:
    id: str
    description: str
    capabilities: frozenset[str]
    risk: str = "low"
    requires_approval: bool = False
    handler: Callable[..., dict[str, Any]] | None = None

    def manifest(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "capabilities": sorted(self.capabilities),
            "risk": self.risk,
            "requires_approval": self.requires_approval,
        }


class KemetAgentToolRegistry:
    VERSION = "1.0"

    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}
        self._register_defaults()

    def register(self, tool: AgentTool) -> None:
        if tool.id in self._tools:
            raise ValueError("agent_tool_already_registered")
        self._tools[tool.id] = tool

    def get(self, tool_id: str) -> AgentTool | None:
        return self._tools.get(tool_id)

    def manifests(self) -> list[dict[str, Any]]:
        return [self._tools[key].manifest() for key in sorted(self._tools)]

    def _register_defaults(self) -> None:
        self.register(AgentTool(
            "business_context",
            "Inspect business objectives, customers, KPI, revenue and cost context.",
            frozenset({"business", "reasoning", "analytics"}),
        ))
        self.register(AgentTool(
            "evidence_research",
            "Retrieve and synthesize knowledge, evidence and business data.",
            frozenset({"knowledge", "research", "evidence"}),
        ))
        self.register(AgentTool(
            "content_strategy",
            "Design governed content intent, offers, audience and creative direction.",
            frozenset({"content", "creation", "business"}),
        ))
        self.register(AgentTool(
            "marketing_intelligence",
            "Research markets, audience signals, campaign strategy, experiments and optimization without external side effects.",
            frozenset({
                "marketing",
                "research",
                "audience",
                "content",
                "analytics",
                "optimization",
                "learning",
                "business",
            }),
        ))
        self.register(AgentTool(
            "production_intelligence",
            "Prepare production, media, asset and quality decisions without executing external side effects.",
            frozenset({"production", "multimedia", "quality"}),
        ))
        self.register(AgentTool(
            "distribution_strategy",
            "Prepare governed distribution and publication plans with evidence requirements.",
            frozenset({"distribution", "publishing", "evidence"}),
            risk="high",
            requires_approval=True,
        ))
        self.register(AgentTool(
            "revenue_intelligence",
            "Analyze offers, leads, payment, fulfillment, revenue and profit signals.",
            frozenset({"revenue", "sales", "business"}),
        ))
        self.register(AgentTool(
            "outcome_learning",
            "Review outcomes, evidence quality and learning signals for the next action.",
            frozenset({"outcome", "learning", "analytics"}),
        ))
        self.register(AgentTool(
            "execution_proposal",
            "Convert an approved plan into a canonical execution proposal; never execute by itself.",
            frozenset({"execution", "governance"}),
            risk="high",
            requires_approval=True,
        ))


kemet_agent_tool_registry = KemetAgentToolRegistry()
