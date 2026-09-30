from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.demo_lead import DemoLead
from app.services.lead_scoring_service import calculate_lead_score, classify_lead


class SalesSupportCommandCenter:
    VERSION = "1.0"
    LIMIT = 5

    def snapshot(self, *, organization_id: int) -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_required")

        now = datetime.utcnow()
        leads = (
            DemoLead.query
            .filter(DemoLead.organization_id == int(organization_id))
            .order_by(DemoLead.updated_at.desc())
            .all()
        )

        prioritized = []
        for lead in leads:
            score = int(calculate_lead_score(lead))
            temperature = classify_lead(score)
            overdue = bool(lead.next_follow_up_at and lead.next_follow_up_at <= now)
            priority_score = score + (10 if overdue else 0)
            prioritized.append({
                "id": lead.id,
                "company_name": lead.company_name,
                "status": lead.status,
                "score": score,
                "temperature": temperature,
                "estimated_value": float(lead.estimated_value or 0),
                "next_follow_up_at": lead.next_follow_up_at.isoformat() if lead.next_follow_up_at else None,
                "overdue": overdue,
                "priority_score": priority_score,
            })

        prioritized.sort(
            key=lambda item: (item["priority_score"], item["estimated_value"]),
            reverse=True,
        )
        hot = sum(item["temperature"] == "hot" for item in prioritized)
        due = sum(item["overdue"] for item in prioritized)
        pipeline_value = sum(item["estimated_value"] for item in prioritized if item["status"] not in {"lost", "converted"})
        top_leads = prioritized[: self.LIMIT]

        for item in top_leads:
            item["recommended_action"] = (
                "follow_up_now" if item["overdue"] else
                "prioritize" if item["temperature"] == "hot" else
                "monitor"
            )
            item["distribution"] = {
                "queue": "sales",
                "recommended_owner_pending": True,
                "mode": "advisory",
            }
            item.pop("priority_score", None)

        return {
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "top_leads": top_leads,
            "hot_leads": int(hot),
            "follow_ups_due": int(due),
            "total_leads": len(prioritized),
            "pipeline_value": round(pipeline_value, 2),
            "recommended_action": "follow_up_now" if due else ("prioritize" if hot else "review_pipeline"),
            "governance": {
                "mode": "advisory",
                "read_only": True,
                "approval_required": True,
                "external_execution": False,
            },
        }


sales_support_command_center = SalesSupportCommandCenter()
