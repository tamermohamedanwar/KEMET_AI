from typing import Any, Dict, List


class RevenueEngine:
    """Canonical dependency-light revenue analysis and decision kernel."""

    PRIORITY_WEIGHT = {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0}

    @staticmethod
    def normalize_score(value: Any) -> int:
        try:
            return max(0, min(int(value or 0), 100))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def normalize_value(value: Any) -> float:
        try:
            return max(float(value or 0), 0.0)
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def decide_lead(cls, *, score: Any = 0, estimated_value: Any = 0.0,
                    status: Any = "new", follow_up_at: Any = None,
                     now: Any = None) -> Dict[str, Any]:
        from datetime import datetime
        now = now or datetime.utcnow()
        score = cls.normalize_score(score)
        estimated_value = cls.normalize_value(estimated_value)
        status = str(status or "new").strip().lower()

        if status in {"won", "converted", "lost"}:
            return {"priority": "none", "action": "monitor",
                    "reason": "Lead is already closed.", "score": score,
                    "estimated_value": estimated_value}
        if follow_up_at and follow_up_at < now:
            return {"priority": "critical", "action": "follow_up_now",
                    "reason": "Follow-up is overdue.", "score": score,
                    "estimated_value": estimated_value}
        if score >= 80 and estimated_value >= 1000:
            return {"priority": "critical", "action": "sales_contact",
                    "reason": "High-intent high-value opportunity.", "score": score,
                    "estimated_value": estimated_value}
        if score >= 75:
            return {"priority": "high", "action": "sales_follow_up",
                    "reason": "Hot lead requires immediate attention.", "score": score,
                    "estimated_value": estimated_value}
        if estimated_value >= 5000:
            return {"priority": "high", "action": "high_value_follow_up",
                    "reason": "High-value opportunity.", "score": score,
                    "estimated_value": estimated_value}
        if score >= 45:
            return {"priority": "medium", "action": "nurture",
                    "reason": "Warm opportunity should be nurtured.", "score": score,
                    "estimated_value": estimated_value}
        return {"priority": "low", "action": "qualification",
                "reason": "Lead needs qualification before sales effort.",
                "score": score, "estimated_value": estimated_value}

    @classmethod
    def ranking_score(cls, decision: Dict[str, Any]) -> float:
        return (
            cls.PRIORITY_WEIGHT.get(decision.get("priority"), 0) * 10000
            + decision.get("score", 0) * 100
            + min(decision.get("estimated_value", 0.0), 999999)
        )

    @staticmethod
    def analyze(
        leads: int = 0,
        opportunities: int = 0,
        customers: int = 0,
        revenue: float = 0.0,
        pipeline_value: float = 0.0,
    ) -> Dict[str, Any]:
        leads = max(int(leads or 0), 0)
        opportunities = max(int(opportunities or 0), 0)
        customers = max(int(customers or 0), 0)
        revenue = max(float(revenue or 0), 0.0)
        pipeline_value = max(float(pipeline_value or 0), 0.0)
        conversion_rate = round((opportunities / leads) * 100, 2) if leads else 0.0


        if pipeline_value > 0:
            focus, priority = "Convert pipeline into revenue", "high"
        elif leads > opportunities:
            focus, priority = "Improve lead conversion", "medium"
        elif customers == 0 and leads == 0:
            focus, priority = "Generate new opportunities", "medium"
        else:
            focus, priority = "Increase revenue efficiency", "normal"

        return {
            "success": True,
            "engine": "kemet_revenue",
            "version": "1.1",
            "metrics": {
                "leads": leads, "opportunities": opportunities,
                "customers": customers, "revenue": revenue,
                "pipeline_value": pipeline_value,
                "conversion_rate": conversion_rate,
            },
            "decision": {"focus": focus, "priority": priority},
            "mode": "advisory",
            "external_execution": False,
        }

    @staticmethod
    def build_actions(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        decision = snapshot.get("decision", {})
        focus = decision.get("focus", "Review revenue")
        priority = decision.get("priority", "normal")
        return [{
            "action": "revenue_review",
            "title": focus,
            "priority": priority,
            "requires_approval": True,
        }]

    

def revenue_analysis(**kwargs: Any) -> Dict[str, Any]:
    return RevenueEngine.analyze(**kwargs)
