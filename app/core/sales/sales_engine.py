from typing import Any, Dict, List, Optional


class SalesEngine:
    @staticmethod
    def analyze(
        leads: int = 0,
        qualified_leads: int = 0,
        opportunities: int = 0,
        customers: int = 0,
        pipeline_value: float = 0.0,
        average_deal_value: float = 0.0,
    ) -> Dict[str, Any]:
        leads = max(int(leads or 0), 0)
        qualified_leads = max(int(qualified_leads or 0), 0)
        opportunities = max(int(opportunities or 0), 0)
        customers = max(int(customers or 0), 0)
        pipeline_value = max(float(pipeline_value or 0), 0.0)
        average_deal_value = max(float(average_deal_value or 0), 0.0)

        qualification_rate = (
            round((qualified_leads / leads) * 100, 2)
            if leads else 0.0
        )

        opportunity_rate = (
            round((opportunities / qualified_leads) * 100, 2)
            if qualified_leads else 0.0
        )

        close_rate = (
            round((customers / opportunities) * 100, 2)
            if opportunities else 0.0
        )

        if pipeline_value > 0:
            focus = "Convert qualified opportunities into customers"
            priority = "high"
        elif leads > 0 and qualified_leads < leads:
            focus = "Improve lead qualification"
            priority = "medium"
        elif qualified_leads > 0 and opportunities < qualified_leads:
            focus = "Improve opportunity conversion"
            priority = "medium"
        elif opportunities > 0 and customers < opportunities:
            focus = "Improve closing efficiency"
            priority = "medium"
        else:
            focus = "Generate and qualify new sales opportunities"
            priority = "normal"

        return {
            "success": True,
            "engine": "kemet_sales",
            "version": "1.0",
            "metrics": {
                "leads": leads,
                "qualified_leads": qualified_leads,
                "opportunities": opportunities,
                "customers": customers,
                "pipeline_value": pipeline_value,
                "average_deal_value": average_deal_value,
                "qualification_rate": qualification_rate,
                "opportunity_rate": opportunity_rate,
                "close_rate": close_rate,
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
        focus = decision.get("focus", "Review sales pipeline")
        priority = decision.get("priority", "normal")

        return [
            {
                "action": "sales_pipeline_review",
                "title": focus,
                "priority": priority,
                "requires_approval": True,
                "external_execution": False,
            }
        ]


def sales_analysis(**kwargs: Any) -> Dict[str, Any]:
    return SalesEngine.analyze(**kwargs)
