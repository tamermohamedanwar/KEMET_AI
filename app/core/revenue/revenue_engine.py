from typing import Any, Dict, List


class RevenueEngine:
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

        conversion_rate = (
            round((opportunities / leads) * 100, 2) if leads else 0.0
        )

        if pipeline_value > 0:
            focus = "Convert pipeline into revenue"
            priority = "high"
        elif leads > opportunities:
            focus = "Improve lead conversion"
            priority = "medium"
        elif customers == 0 and leads == 0:
            focus = "Generate new opportunities"
            priority = "medium"
        else:
            focus = "Increase revenue efficiency"
            priority = "normal"

        return {
            "success": True,
            "engine": "kemet_revenue",
            "version": "1.0",
            "metrics": {
                "leads": leads,
                "opportunities": opportunities,
                "customers": customers,
                "revenue": revenue,
                "pipeline_value": pipeline_value,
                "conversion_rate": conversion_rate,
            },
            "decision": {
                "focus": focus,
                "priority": priority,
            },
            "mode": "advisory",
            "external_execution": False,
        }

    @staticmethod
    def build_actions(snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        decision = snapshot.get("decision", {})
        focus = decision.get("focus", "Review revenue")
        priority = decision.get("priority", "normal")

        return [
            {
                "action": "revenue_review",
                "title": focus,
                "priority": priority,
                "requires_approval": True,
            }
        ]


def revenue_analysis(**kwargs: Any) -> Dict[str, Any]:
    return RevenueEngine.analyze(**kwargs)
