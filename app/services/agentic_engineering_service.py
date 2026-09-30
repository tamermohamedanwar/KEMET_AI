from __future__ import annotations

from typing import Any

from app.core.federation.agent_capability_contract import AgentCapabilityContract
from app.services.evaluation_learning import EvaluationLearningService


class AgenticEngineeringService:
    """Kemet-native contract, evaluation and observability boundary for agentic work."""

    VERSION = "1.0"
    LIFECYCLE = (
        "understand", "context", "decide", "plan", "propose",
        "approve", "execute", "evidence", "outcome", "learn",
    )

    @staticmethod
    def contract(*, agent_id: str, provider_id: str = "kemet", kind: str = "business",
                 capabilities=None, authority: str = "governed_submission",
                 execution_authority: bool = False, supports_async: bool = False,
                 metadata=None) -> dict[str, Any]:
        contract = AgentCapabilityContract(
            contract_version="1.0",
            agent_id=str(agent_id or "").strip(),
            provider_id=str(provider_id or "").strip(),
            kind=kind,
            capabilities=frozenset(capabilities or ()),
            authority=authority,
            execution_authority=execution_authority,
            requires_verification=True,
            requires_human_approval=not execution_authority,
            supports_async=supports_async,
            metadata=metadata or {},
        )
        result = contract.as_dict()
        result["lifecycle"] = list(AgenticEngineeringService.LIFECYCLE)
        result["governance"] = AgenticEngineeringService.governance()
        return result

    @staticmethod
    def evaluate(lifecycle: dict[str, Any]) -> dict[str, Any]:
        return EvaluationLearningService.evaluate(lifecycle)

    @staticmethod
    def evaluation_batch(lifecycles) -> dict[str, Any]:
        return EvaluationLearningService.build(lifecycles or [])

    @staticmethod
    def governance() -> dict[str, Any]:
        return {
            "read_only": True,
            "advisory": True,
            "external_execution": False,
            "database_mutation": False,
            "auto_execute": False,
            "human_approval_required": True,
            "canonical_executor": "kemet",
        }

    @staticmethod
    def _context_quality(context: Any) -> dict[str, Any]:
        if not isinstance(context, dict):
            return {
                "available": False, "evidence_count": 0, "source_count": 0,
                "excluded_untrusted": 0, "evidence_digest": None,
            }
        retrieval = context.get("retrieval") or {}
        sources = context.get("sources") or []
        return {
            "available": True,
            "evidence_count": len(sources),
            "source_count": len({str(s.get("filename")) for s in sources if isinstance(s, dict)}),
            "excluded_untrusted": int(retrieval.get("excluded", 0) or 0),
            "evidence_digest": context.get("digest"),
        }

    @staticmethod
    def observability(*, lifecycle: dict[str, Any], evaluation: dict[str, Any] | None = None) -> dict[str, Any]:
        evaluation = evaluation or EvaluationLearningService.evaluate(lifecycle)
        return {
            "version": AgenticEngineeringService.VERSION,
            "decision_id": lifecycle.get("decision_id"),
            "capability_id": lifecycle.get("capability_id"),
            "state": lifecycle.get("state", "detected"),
            "trace": {
                "context": bool(lifecycle.get("context")),
                "plan": bool(lifecycle.get("plan")),
                "proposal": bool(lifecycle.get("proposal")),
                "approval": bool(lifecycle.get("approval")),
                "execution": bool(lifecycle.get("execution")),
                "evidence": bool(lifecycle.get("evidence")),
                "outcome": bool(lifecycle.get("observed_outcome")),
            },
            "context_quality": AgenticEngineeringService._context_quality(lifecycle.get("context")),
            "evaluation": evaluation,
            "governance": AgenticEngineeringService.governance(),
        }


agentic_engineering_service = AgenticEngineeringService()
