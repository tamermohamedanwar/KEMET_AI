from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.federation.research_engine import ResearchEngine
from app.core.federation.executive_brief import executive_brief
from app.core.federation.decision_control import decision_control


@dataclass(frozen=True)
class ResearchWorkflow:
    workflow_id: str
    name: str
    description: str
    default_sources: tuple[str, ...]
    focus: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "default_sources": list(self.default_sources),
            "focus": list(self.focus),
        }


WORKFLOWS = (
    ResearchWorkflow(
        "market_intelligence", "Market Intelligence",
        "Structured market signals, demand, competitors and opportunities.",
        ("web_search", "reddit", "youtube"),
        ("market_size", "demand", "pricing", "competitors", "opportunities"),
    ),
    ResearchWorkflow(
        "competitor_radar", "Competitor Radar",
        "Evidence-led monitoring of competitors, products, positioning and signals.",
        ("web_search", "reddit", "youtube", "github"),
        ("competitors", "product", "pricing", "positioning", "changes"),
    ),
    ResearchWorkflow(
        "customer_voice", "Customer Voice",
        "Customer discussions, complaints, needs and recurring sentiment signals.",
        ("reddit", "youtube", "web_search"),
        ("needs", "complaints", "sentiment", "requests", "pain_points"),
    ),
    ResearchWorkflow(
        "trend_radar", "Trend Radar",
        "Emerging technology, market and social signals with source corroboration.",
        ("web_search", "reddit", "youtube", "twitter"),
        ("emerging", "momentum", "adoption", "risk", "opportunity"),
    ),
)


class ResearchWorkflowService:
    VERSION = "1.0"

    def __init__(self, engine: ResearchEngine | None = None):
        self.engine = engine or ResearchEngine()
        self._workflows = {item.workflow_id: item for item in WORKFLOWS}

    def catalog(self) -> list[dict[str, Any]]:
        return [item.as_dict() for item in WORKFLOWS]

    def get(self, workflow_id: str) -> ResearchWorkflow:
        key = str(workflow_id or "").strip().lower()
        if key not in self._workflows:
            raise ValueError("unsupported_research_workflow")
        return self._workflows[key]

    def prepare(self, workflow_id: str, question: str) -> dict[str, Any]:
        workflow = self.get(workflow_id)
        plan = self.engine.plan(question, workflow.default_sources)
        return {
            "version": self.VERSION,
            "workflow": workflow.as_dict(),
            "plan": plan,
            "governance": {
                "read_only": True,
                "external_execution": False,
                "database_mutation": False,
                "auto_execute": False,
                "human_approval_required_for_actions": True,
            },
        }


    def run(self, workflow_id: str, question: str, **kwargs: Any) -> dict[str, Any]:
        workflow = self.get(workflow_id)
        requested = kwargs.pop("source_ids", None) or workflow.default_sources
        result = self.engine.run(question, source_ids=requested, **kwargs)
        result["workflow"] = workflow.as_dict()
        result["synthesis"] = self.engine.synthesize(result)
        result["governance"]["human_review_required"] = True
        task_id = str(kwargs.get("task_id") or "research")
        organization_id = int(kwargs.get("organization_id") or 0)
        result["executive_brief"] = executive_brief.build(
            task_id=task_id,
            organization_id=organization_id,
            question=question,
            research=result,
        )
        result["decision_record"] = decision_control.create(
            task_id=task_id,
            organization_id=organization_id,
            brief=result["executive_brief"],
            project_context_hash=str(kwargs.get("project_context_hash") or ""),
            plan_hash=str(kwargs.get("plan_hash") or ""),
        )
        result["governance"]["decision_status"] = "review_required"
        result["governance"]["decision_digest"] = result["decision_record"]["digest"]
        return result

research_workflows = ResearchWorkflowService()
