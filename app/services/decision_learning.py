from __future__ import annotations

from typing import Any

from app.services.capability_registry import capability_registry
from app.services.decision_lifecycle import DecisionLifecycleService
from app.services.outcome_intelligence import outcome_intelligence


class DecisionLearningService:
    """Read-only observational learning signals for governed decisions."""

    VERSION = "1.0"

    @classmethod
    def _capability(cls, decision: dict[str, Any]) -> str | None:
        action = str(decision.get("action") or decision.get("executable_action") or "").strip()
        capability_id = decision.get("capability_id") or (f"kemet.{action}" if action else None)
        return capability_id if capability_id and capability_registry.get(capability_id) else None

    @classmethod
    def _state_counts(cls, items: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in items:
            state = str(item.get("state") or "detected")
            counts[state] = counts.get(state, 0) + 1
        return counts

    @classmethod
    def _signals(cls, organization_id: int, decisions: list[dict[str, Any]], period: str):
        lifecycle = DecisionLifecycleService.project(organization_id, decisions, period=period)
        items = lifecycle.get("items", []) if lifecycle.get("success") else []
        counts = cls._state_counts(items)
        total = len(items)
        approved = counts.get("approved", 0) + counts.get("executed", 0) + counts.get("outcome_observed", 0)
        executed = counts.get("executed", 0) + counts.get("outcome_observed", 0)
        observed = counts.get("outcome_observed", 0)
        approval_rate = round(approved / total, 4) if total else 0.0
        execution_rate = round(executed / approved, 4) if approved else 0.0
        observed_rate = round(observed / executed, 4) if executed else 0.0
        return items, {
            "decision_count": total,
            "approved_count": approved,
            "executed_count": executed,
            "outcome_observed_count": observed,
            "approval_rate": approval_rate,
            "execution_success_rate": execution_rate,
            "outcome_observed_rate": observed_rate,
        }

    @classmethod
    def build(cls, organization_id: int | None, decisions: list[dict[str, Any]] | None = None, period: str = "30d") -> dict[str, Any]:
        if not organization_id:
            return {"success": False, "error": "organization_required", "engine": "kemet_decision_learning", "version": cls.VERSION}
        supplied = [item for item in (decisions or []) if isinstance(item, dict)]
        items, aggregate = cls._signals(organization_id, supplied, period)
        by_capability: dict[str, dict[str, Any]] = {}
        for item in items:
            capability_id = item.get("capability_id") or cls._capability(item)
            if not capability_id:
                continue
            bucket = by_capability.setdefault(capability_id, {"capability_id": capability_id, "decisions": 0, "approved": 0, "executed": 0, "outcome_observed": 0})
            bucket["decisions"] += 1
            state = item.get("state")
            if state in {"approved", "executed", "outcome_observed"}:
                bucket["approved"] += 1
            if state in {"executed", "outcome_observed"}:
                bucket["executed"] += 1
            if state == "outcome_observed":
                bucket["outcome_observed"] += 1
        for bucket in by_capability.values():
            total = bucket["decisions"]
            approved = bucket["approved"]
            executed = bucket["executed"]
            bucket["approval_rate"] = round(bucket["approved"] / total, 4) if total else 0.0
            bucket["execution_rate"] = round(executed / approved, 4) if approved else 0.0
            bucket["outcome_observed_rate"] = round(bucket["outcome_observed"] / executed, 4) if executed else 0.0
        return {
            "success": True,
            "engine": "kemet_decision_learning",
            "version": cls.VERSION,
            "organization_id": organization_id,
            "period": period,
            "aggregate": aggregate,
            "capabilities": list(by_capability.values()),
            "decision_history": items,
            "learning": {
                "mode": "observational",
                "inputs": ["decision_lifecycle", "approval_history", "execution_history", "outcome_observation"],
                "ranking_adjustment": "recommendation_only",
                "confidence_calibration": True,
                "causal_claim": False,
                "roi_claim": False,
            },
            "governance": {
                "read_only": True,
                "advisory": True,
                "external_execution": False,
                "database_mutation": False,
                "auto_execute": False,
            },
        }

    @classmethod
    def enrich(cls, organization_id: int | None, decisions: list[dict[str, Any]], period: str = "30d") -> dict[str, Any]:
        learning = cls.build(organization_id, decisions, period)
        if not learning.get("success"):
            return learning
        lookup = {item["capability_id"]: item for item in learning.get("capabilities", [])}
        enriched = []
        for decision in decisions or []:
            capability_id = cls._capability(decision)
            signal = lookup.get(capability_id, {})
            outcome_rate = float(signal.get("outcome_observed_rate", 0.0) or 0.0)
            execution_rate = float(signal.get("execution_rate", 0.0) or 0.0)
            learning_factor = round((0.6 * outcome_rate) + (0.4 * execution_rate), 4)
            confidence_adjustment = round((learning_factor - 0.5) * 0.20, 4)
            enriched.append({
                **decision,
                "learning_signal": {
                    "capability_id": capability_id,
                    "sample_size": signal.get("decisions", 0),
                    "approval_rate": signal.get("approval_rate", 0.0),
                    "execution_rate": execution_rate,
                    "outcome_observed_rate": outcome_rate,
                    "learning_factor": learning_factor,
                    "confidence_adjustment": confidence_adjustment,
                    "mode": "observational",
                },
            })
        learning["decisions"] = enriched
        return learning



decision_learning = DecisionLearningService()
