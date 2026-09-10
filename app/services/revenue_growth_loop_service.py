from datetime import datetime

from app.services.revenue_decision_service import (
    RevenueDecisionService,
)


class RevenueGrowthLoopService:

    ACTIONS = {
        "critical": "revenue_autopilot_run",
        "high": "sales_follow_up",
        "medium": "customer_nurture",
        "low": "lead_qualification",
        "none": "monitor",
    }

    @classmethod
    def build(cls, lead, now=None):
        now = now or datetime.utcnow()

        decision = RevenueDecisionService.decide(
            lead,
            now=now,
        )

        priority = decision["priority"]
        action = cls.ACTIONS.get(
            priority,
            "monitor",
        )

        return {
            "lead_id": lead.id,
            "company_name": (
                lead.company_name
                or "Unnamed company"
            ),
            "priority": priority,
            "decision": decision,
            "recommended_action": action,
            "estimated_value": decision[
                "estimated_value"
            ],
            "lead_score": decision["score"],
            "ready_for_autopilot": (
                priority in {
                    "critical",
                    "high",
                }
            ),
        }

    @classmethod
    def build_batch(cls, leads, limit=100):
        results = []

        for lead in list(leads or [])[:limit]:
            results.append(
                cls.build(lead)
            )

        results.sort(
            key=lambda item: (
                {
                    "critical": 4,
                    "high": 3,
                    "medium": 2,
                    "low": 1,
                    "none": 0,
                }.get(
                    item["priority"],
                    0,
                ),
                item["lead_score"],
                item["estimated_value"],
            ),
            reverse=True,
        )

        return results

    @classmethod
    def summarize(cls, leads):
        items = cls.build_batch(leads)

        summary = {
            "total": len(items),
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "none": 0,
            "autopilot_ready": 0,
            "estimated_revenue": 0.0,
        }

        for item in items:
            priority = item["priority"]

            if priority in summary:
                summary[priority] += 1

            if item["ready_for_autopilot"]:
                summary["autopilot_ready"] += 1

            if priority != "none":
                summary["estimated_revenue"] += (
                    item["estimated_value"]
                )

        summary["estimated_revenue"] = round(
            summary["estimated_revenue"],
            2,
        )

        return {
            "summary": summary,
            "items": items,
        }
