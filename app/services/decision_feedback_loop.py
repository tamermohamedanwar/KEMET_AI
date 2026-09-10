from datetime import datetime
from typing import Any


class DecisionFeedbackLoopService:
    VERSION = "1.1"
    SIGNALS = ("positive", "neutral", "negative")

    @classmethod
    def build(cls, feedback_items: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        items = []
        for item in feedback_items or []:
            if not isinstance(item, dict):
                continue
            signal = str(item.get("signal") or "neutral").strip().lower()
            if signal not in cls.SIGNALS:
                continue
            items.append({"decision_id": item.get("decision_id"), "capability_id": item.get("capability_id"), "signal": signal})
        counts = {signal: sum(1 for item in items if item["signal"] == signal) for signal in cls.SIGNALS}
        total = len(items)
        weighted = (counts["positive"] - counts["negative"]) / total if total else 0.0
        return {
            "success": True,
            "engine": "kemet_decision_feedback_loop",
            "version": cls.VERSION,
            "feedback_count": total,
            "signals": counts,
            "learning_signal": round(weighted, 4),
            "confidence": round(min(total / 10.0, 1.0), 4),
            "mode": "observational",
            "ranking_adjustment": "recommendation_only",
            "governance": {"read_only": True, "advisory": True, "external_execution": False, "database_mutation": False, "auto_execute": False, "human_approval_required": True},
            "generated_at": datetime.utcnow().isoformat(),
        }


decision_feedback_loop = DecisionFeedbackLoopService()
