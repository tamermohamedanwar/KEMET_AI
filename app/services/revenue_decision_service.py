from datetime import datetime, timedelta

from app.core.revenue.revenue_engine import RevenueEngine


class RevenueDecisionService:

    @staticmethod
    def _score(lead):
        return RevenueEngine.normalize_score(getattr(lead, "lead_score", 0))

    @staticmethod
    def _value(lead):
        return RevenueEngine.normalize_value(getattr(lead, "estimated_value", 0))

    @staticmethod
    def _status(lead):
        return str(getattr(lead, "status", None) or "new").strip().lower()

    @classmethod
    def decide(cls, lead, now=None):
        return RevenueEngine.decide_lead(score=getattr(lead, "lead_score", 0), estimated_value=getattr(lead, "estimated_value", 0), status=getattr(lead, "status", "new"), follow_up_at=getattr(lead, "next_follow_up_at", None), now=now)

    @classmethod
    def rank(cls, leads):
        ranked = []

        for lead in list(leads or []):
            decision = cls.decide(lead)

            weighted_score = RevenueEngine.ranking_score(decision)

            qualification_status = str(
                getattr(lead, "qualification_status", None) or ""
            ).strip().lower()
            commercially_qualified = qualification_status == "commercial_qualified"
            decision = {
                **decision,
                "commercially_qualified": commercially_qualified,
                "forecast_only": True,
                "revenue_authority": "lead_estimated_value_forecast_not_realized_revenue",
            }

            ranked.append(
                {
                    "lead_id": lead.id,
                    "company_name": (
                        lead.company_name
                        or "Unnamed company"
                    ),
                    "decision": decision,
                    "ranking_score": round(
                        weighted_score,
                        2,
                    ),
                }
            )

        ranked.sort(
            key=lambda item: item["ranking_score"],
            reverse=True,
        )

        return ranked

class RevenueEventService:
    EVENT_LEAD_HOT = "lead.hot"
    EVENT_LEAD_HIGH_VALUE = "lead.high_value"
    EVENT_LEAD_FOLLOWUP_DUE = "lead.followup_due"
    EVENT_LEAD_FOLLOWUP_OVERDUE = "lead.followup_overdue"
    EVENT_LEAD_STALE = "lead.stale"
    EVENT_LEAD_CONVERTED = "lead.converted"

    @classmethod
    def build_events(cls, lead, now=None):
        from datetime import timedelta
        now = now or datetime.utcnow()
        status = RevenueDecisionService._status(lead)
        score = RevenueDecisionService._score(lead)
        value = RevenueDecisionService._value(lead)
        base = {
            "lead_id": lead.id,
            "organization_id": lead.organization_id,
            "company_name": lead.company_name or "Unnamed company",
            "estimated_value": value,
            "lead_score": score,
            "qualification_status": getattr(lead, "qualification_status", None) or "",
            "commercially_qualified": str(getattr(lead, "qualification_status", None) or "").strip().lower() == "commercial_qualified",
            "forecast_only": True,
            "revenue_authority": "lead_estimated_value_forecast_not_realized_revenue",
            "created_at": now.isoformat(),
        }
        events = []
        if status in {"won", "converted"}:
            events.append({"event": cls.EVENT_LEAD_CONVERTED, "data": base})
        if status not in {"won", "converted", "lost"}:
            if score >= 75:
                events.append({"event": cls.EVENT_LEAD_HOT, "data": base})
            if value >= 1000:
                events.append({"event": cls.EVENT_LEAD_HIGH_VALUE, "data": base})
            follow_up = getattr(lead, "next_follow_up_at", None)
            if follow_up and follow_up < now:
                events.append({"event": cls.EVENT_LEAD_FOLLOWUP_OVERDUE, "data": base})
            elif follow_up and follow_up.date() == now.date():
                events.append({"event": cls.EVENT_LEAD_FOLLOWUP_DUE, "data": base})
            created_at = getattr(lead, "created_at", None)
            if created_at and now >= created_at + timedelta(days=7) and score < 45:
                events.append({"event": cls.EVENT_LEAD_STALE, "data": base})
        return events


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
        decision = RevenueDecisionService.decide(lead, now=now)
        qualification_status = str(getattr(lead, "qualification_status", None) or "").strip().lower()
        commercially_qualified = qualification_status == "commercial_qualified"
        return {
            "lead_id": lead.id,
            "company_name": lead.company_name or "Unnamed company",
            "priority": decision["priority"],
            "decision": decision,
            "recommended_action": cls.ACTIONS.get(decision["priority"], "monitor"),
            "estimated_value": decision["estimated_value"],
            "lead_score": decision["score"],
            "ready_for_autopilot": decision["priority"] in {"critical", "high"} and commercially_qualified,
            "commercially_qualified": commercially_qualified,
            "forecast_only": True,
            "revenue_authority": "lead_estimated_value_forecast_not_realized_revenue",
        }

    @classmethod
    def build_batch(cls, leads, limit=100):
        items = [cls.build(lead) for lead in list(leads or [])[:limit]]
        items.sort(
            key=lambda item: (
                {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0}.get(item["priority"], 0),
                item["lead_score"],
                item["estimated_value"],
            ),
            reverse=True,
        )
        return items

    @classmethod
    def summarize(cls, leads):
        items = cls.build_batch(leads)
        summary = {"total": len(items), "critical": 0, "high": 0, "medium": 0, "low": 0, "none": 0, "autopilot_ready": 0, "estimated_revenue": 0.0}
        for item in items:
            if item["priority"] in summary:
                summary[item["priority"]] += 1
            if item["ready_for_autopilot"]:
                summary["autopilot_ready"] += 1
            if item["priority"] != "none":
                summary["estimated_revenue"] += item["estimated_value"]
        summary["estimated_revenue"] = round(summary["estimated_revenue"], 2)
        return {
            "summary": summary,
            "items": items,
            "measurement": {
                "estimated_revenue_is_forecast": True,
                "realized_revenue_authority": "revenue_pipeline_verified_payment_binding",
                "auto_execute": False,
                "external_execution": False,
            },
        }
