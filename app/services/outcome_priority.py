from __future__ import annotations

from typing import Any

from app.services.outcome_intelligence import outcome_intelligence
from app.services.capability_registry import capability_registry


class OutcomePriorityService:
    """Rank advisory next-best actions by observed signal and confidence."""

    VERSION = "1.0"
    PRIORITY_WEIGHT = {"critical": 1.0, "high": 0.85, "medium": 0.65, "low": 0.45}

    @classmethod
    def _impact_strength(cls, item: dict[str, Any]) -> float:
        values = []
        for signal in item.get("observed_impact", []):
            delta = signal.get("delta")
            if isinstance(delta, (int, float)):
                values.append(min(abs(float(delta)), 100.0) / 100.0)
        return min(max(values or [0.0]), 1.0)

    @classmethod
    def rank(cls, organization_id: int | None, decisions: list[dict[str, Any]], period: str = "30d") -> dict[str, Any]:
        if not organization_id:
            return {"success": False, "error": "organization_required", "engine": "kemet_outcome_priority", "version": cls.VERSION}
        ranked = []
        for decision in decisions or []:
            action = decision.get("action") or decision.get("executable_action")
            capability_id = decision.get("capability_id") or (f"kemet.{action}" if action else None)
            if not capability_id or not capability_registry.get(capability_id):
                continue
            intelligence = outcome_intelligence.build(organization_id, capability_id, period)
            if not intelligence.get("success"):
                continue
            confidence = float((intelligence.get("confidence") or {}).get("score", 0.0) or 0.0)
            impact = cls._impact_strength(intelligence)
            priority = str(decision.get("priority") or "low").lower()
            priority_score = cls.PRIORITY_WEIGHT.get(priority, cls.PRIORITY_WEIGHT["low"])
            score = round((0.45 * priority_score) + (0.35 * confidence) + (0.20 * impact), 4)
            ranked.append({
                **decision,
                "capability_id": capability_id,
                "observed_impact": intelligence.get("observed_impact", []),
                "impact_confidence": intelligence.get("confidence", {}),
                "priority_score": priority_score,
                "impact_strength": round(impact, 4),
                "outcome_priority_score": score,
                "ranking": "advisory",
            })
        ranked.sort(key=lambda item: item["outcome_priority_score"], reverse=True)
        return {
            "success": True,
            "engine": "kemet_outcome_priority",
            "version": cls.VERSION,
            "organization_id": organization_id,
            "period": period,
            "items": ranked,
            "count": len(ranked),
            "governance": {"read_only": True, "advisory": True, "causal_claim": False, "roi_claim": False, "external_execution": False, "database_mutation": False},
        }


outcome_priority = OutcomePriorityService()
