from typing import Any, Dict


class ROIEngine:
    @staticmethod
    def calculate(
        revenue: float = 0.0,
        cost: float = 0.0,
        customers: int = 0,
        leads: int = 0,
        automated_tasks: int = 0,
        manual_hours_saved: float = 0.0,
    ) -> Dict[str, Any]:
        revenue = max(float(revenue or 0), 0.0)
        cost = max(float(cost or 0), 0.0)
        customers = max(int(customers or 0), 0)
        leads = max(int(leads or 0), 0)
        automated_tasks = max(int(automated_tasks or 0), 0)
        manual_hours_saved = max(float(manual_hours_saved or 0), 0.0)

        net_value = revenue - cost
        roi_percent = round((net_value / cost) * 100, 2) if cost else 0.0
        revenue_per_customer = (
            round(revenue / customers, 2) if customers else 0.0
        )
        lead_to_customer_rate = (
            round((customers / leads) * 100, 2) if leads else 0.0
        )

        if roi_percent >= 200:
            health = "excellent"
            focus = "Scale high-performing operations"
        elif roi_percent >= 100:
            health = "strong"
            focus = "Scale profitable workflows"
        elif roi_percent > 0:
            health = "positive"
            focus = "Improve operational efficiency"
        else:
            health = "needs_attention"
            focus = "Reduce cost and improve conversion"

        return {
            "success": True,
            "engine": "kemet_roi",
            "version": "1.0",
            "metrics": {
                "revenue": revenue,
                "cost": cost,
                "net_value": net_value,
                "roi_percent": roi_percent,
                "customers": customers,
                "leads": leads,
                "automated_tasks": automated_tasks,
                "manual_hours_saved": manual_hours_saved,
                "revenue_per_customer": revenue_per_customer,
                "lead_to_customer_rate": lead_to_customer_rate,
            },
            "decision": {
                "health": health,
                "focus": focus,
            },
            "mode": "advisory",
            "external_execution": False,
            "database_mutation": False,
        }

    @staticmethod
    def build_report(snapshot: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "success": bool(snapshot.get("success")),
            "engine": "kemet_roi",
            "summary": snapshot.get("decision", {}),
            "metrics": snapshot.get("metrics", {}),
            "requires_approval": True,
            "external_execution": False,
        }


def roi_analysis(**kwargs: Any) -> Dict[str, Any]:
    return ROIEngine.calculate(**kwargs)
