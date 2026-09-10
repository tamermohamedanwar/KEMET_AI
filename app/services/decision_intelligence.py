from __future__ import annotations

from typing import Any

from app.services.decision_learning import decision_learning


class DecisionIntelligenceService:
    """Read-only unified score for advisory decision review ordering."""

    VERSION = "1.0"

    @classmethod
    def score(cls, decision: dict[str, Any], learning_signal: dict[str, Any]) -> dict[str, Any]:
        priority = str(decision.get("priority") or "low").lower()
        priority_base = {"critical": 1.0, "high": 0.85, "medium": 0.65, "low": 0.45}.get(priority, 0.45)
        confidence = float(decision.get("confidence") or 0.0)
        learning_factor = float(learning_signal.get("learning_factor") or 0.0)
        impact = float(decision.get("impact") or 0.0)
        impact_base = min(abs(impact), 100.0) / 100.0
        raw = (0.40 * priority_base) + (0.30 * confidence) + (0.20 * learning_factor) + (0.10 * impact_base)
        adjustment = float(learning_signal.get("confidence_adjustment") or 0.0)
        final = round(min(max(raw + adjustment, 0.0), 1.0), 4)
        level = "critical" if final >= .85 else "high" if final >= .70 else "medium" if final >= .50 else "low"
        return {"score": final, "level": level, "confidence_adjustment": round(adjustment, 4), "method": "advisory_weighted"}

    @classmethod
    def build(cls, organization_id: int | None, decisions: list[dict[str, Any]] | None = None, period: str = "30d") -> dict[str, Any]:
        if not organization_id:
            return {"success": False, "error": "organization_required", "engine": "kemet_decision_intelligence", "version": cls.VERSION}
        learning = decision_learning.enrich(organization_id, decisions or [], period=period)
        if not learning.get("success"):
            return learning
        ranked = []
        for decision in learning.get("decisions", []):
            signal = decision.get("learning_signal", {})
            intelligence = cls.score(decision, signal)
            ranked.append({**decision, "decision_intelligence": intelligence})
        ranked.sort(key=lambda item: item["decision_intelligence"]["score"], reverse=True)
        return {
            "success": True,
            "engine": "kemet_decision_intelligence",
            "version": cls.VERSION,
            "organization_id": organization_id,
            "period": period,
            "decisions": ranked,
            "count": len(ranked),
            "governance": {"read_only": True, "advisory": True, "causal_claim": False, "roi_claim": False, "external_execution": False, "database_mutation": False, "auto_execute": False, "human_approval_required": True},
        }



decision_intelligence = DecisionIntelligenceService()
