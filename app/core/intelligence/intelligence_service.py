from dataclasses import dataclass, asdict
from typing import Any, Dict, List


@dataclass
class IntelligenceSignal:
    key: str
    title: str
    priority: str
    category: str
    message: str
    action: str
    confidence: float = 0.0
    source: str = "kemet"


class IntelligenceService:
    PRIORITY_ORDER = {
        "critical": 0,
        "high": 1,
        "medium": 2,
        "low": 3,
        "info": 4,
    }

    @classmethod
    def _normalize_signal(cls, signal: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "key": str(signal.get("key") or signal.get("id") or "signal"),
            "title": str(signal.get("title") or signal.get("name") or "Business Signal"),
            "priority": str(signal.get("priority") or "info").lower(),
            "category": str(signal.get("category") or "general"),
            "message": str(signal.get("message") or ""),
            "action": str(signal.get("action") or signal.get("next_best_action") or ""),
            "confidence": float(signal.get("confidence") or 0.0),
            "source": str(signal.get("source") or "kemet"),
        }

    @classmethod
    def rank_signals(cls, signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        normalized = [cls._normalize_signal(item) for item in signals]
        return sorted(
            normalized,
            key=lambda item: (
                cls.PRIORITY_ORDER.get(item["priority"], 99),
                -item["confidence"],
            ),
        )

    @classmethod
    def summarize(cls, signals: List[Dict[str, Any]]) -> Dict[str, Any]:
        ranked = cls.rank_signals(signals)

        counts = {}
        for signal in ranked:
            priority = signal["priority"]
            counts[priority] = counts.get(priority, 0) + 1

        top = ranked[0] if ranked else None

        return {
            "success": True,
            "signal_count": len(ranked),
            "priority_counts": counts,
            "top_signal": top,
            "focus": (
                top["action"]
                if top and top.get("action")
                else (
                    top["message"]
                    if top
                    else "Business operations are currently stable."
                )
            ),
            "signals": ranked[:10],
        }

    @classmethod
    def build_snapshot(
        cls,
        organization_id=None,
        signals=None,
        context=None,
    ) -> Dict[str, Any]:
        signals = signals or []
        summary = cls.summarize(signals)

        return {
            "success": True,
            "organization_id": organization_id,
            "engine": "kemet_intelligence",
            "version": "1.0",
            "mode": "advisory",
            "context": context or {},
            "summary": summary,
        }


def intelligence_snapshot(
    organization_id=None,
    signals=None,
    context=None,
) -> Dict[str, Any]:
    return IntelligenceService.build_snapshot(
        organization_id=organization_id,
        signals=signals,
        context=context,
    )
