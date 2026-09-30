from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any

from app.models.demo_lead import DemoLead
from app.models.ticket import Ticket
from app.models.user import User


@dataclass(frozen=True)
class DistributionRecommendation:
    entity_type: str
    entity_id: int
    organization_id: int
    queue: str
    owner_id: int | None
    owner_name: str | None
    reason: str
    workload: int
    priority: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "organization_id": self.organization_id,
            "queue": self.queue,
            "owner_id": self.owner_id,
            "owner_name": self.owner_name,
            "reason": self.reason,
            "workload": self.workload,
            "priority": self.priority,
        }


class DistributionService:
    VERSION = "1.0"
    MAX_RECOMMENDATIONS = 5

    @staticmethod
    def _fingerprint(value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def preview_sales(self, *, organization_id: int, limit: int | None = None) -> dict[str, Any]:
        organization_id = int(organization_id)
        if organization_id <= 0:
            raise ValueError("organization_required")
        limit = max(1, min(int(limit or self.MAX_RECOMMENDATIONS), self.MAX_RECOMMENDATIONS))

        users = (
            User.query
            .filter(User.organization_id == organization_id)
            .order_by(User.id.asc())
            .all()
        )
        lead_load = {int(user.id): 0 for user in users}
        ticket_load = {int(user.id): 0 for user in users}
        for lead in DemoLead.query.filter(DemoLead.organization_id == organization_id).all():
            if lead.owner_id in lead_load and lead.status not in {"lost", "converted"}:
                lead_load[int(lead.owner_id)] += 1
        for ticket in Ticket.query.filter(
            Ticket.organization_id == organization_id,
            Ticket.status.notin_(["closed", "resolved"]),
        ).all():
            if ticket.assigned_to_id in ticket_load:
                ticket_load[int(ticket.assigned_to_id)] += 1

        candidates = {
            int(user.id): {
                "user": user,
                "workload": lead_load[int(user.id)] + ticket_load[int(user.id)],
                "lead_load": lead_load[int(user.id)],
                "ticket_load": ticket_load[int(user.id)],
            }
            for user in users
        }

        leads = (
            DemoLead.query
            .filter(DemoLead.organization_id == organization_id)
            .filter(DemoLead.status.notin_(["lost", "converted"]))
            .order_by(DemoLead.updated_at.desc())
            .all()
        )
        ranked = []
        for lead in leads:
            overdue = bool(lead.next_follow_up_at and lead.next_follow_up_at <= __import__("datetime").datetime.utcnow())
            priority = int(lead.lead_score or 0) + (10 if overdue else 0)
            ranked.append((priority, float(lead.estimated_value or 0), lead))
        ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)

        recommendations = []
        for priority, _, lead in ranked[:limit]:
            current_owner = candidates.get(int(lead.owner_id)) if lead.owner_id else None
            if current_owner:
                selected = current_owner
                reason = "retain_existing_owner"
            elif candidates:
                selected = min(
                    candidates.values(),
                    key=lambda item: (item["workload"], item["ticket_load"], item["user"].id),
                )
                reason = "lowest_workload_match"
            else:
                selected = None
                reason = "no_eligible_user"
            recommendations.append(DistributionRecommendation(
                entity_type="lead",
                entity_id=int(lead.id),
                organization_id=organization_id,
                queue="sales",
                owner_id=int(selected["user"].id) if selected else None,
                owner_name=selected["user"].full_name if selected else None,
                reason=reason,
                workload=int(selected["workload"]) if selected else 0,
                priority=priority,
            ).as_dict())

        payload = {
            "version": self.VERSION,
            "organization_id": organization_id,
            "recommendations": recommendations,
            "candidate_count": len(candidates),
            "governance": {
                "mode": "advisory",
                "read_only": True,
                "approval_required": True,
                "external_execution": False,
                "database_mutation": False,
            },
        }
        payload["fingerprint"] = self._fingerprint(payload)
        return payload


distribution_service = DistributionService()
