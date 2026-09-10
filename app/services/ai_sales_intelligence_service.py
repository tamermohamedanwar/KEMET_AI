from datetime import datetime


class AISalesIntelligenceService:
    """
    Deterministic sales intelligence layer.

    This service prepares structured sales decisions that can later
    be consumed by an AI provider or the Automation Engine.
    """

    HOT_SCORE = 75
    WARM_SCORE = 45

    @staticmethod
    def _score(lead):
        try:
            return max(
                0,
                min(
                    int(lead.lead_score or 0),
                    100,
                ),
            )
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _value(lead):
        try:
            return float(
                lead.estimated_value or 0
            )
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _status(lead):
        return (
            lead.status or "new"
        ).strip().lower()

    @classmethod
    def classify_lead(cls, lead):
        status = cls._status(lead)
        score = cls._score(lead)
        value = cls._value(lead)

        if status in {
            "won",
            "converted",
        }:
            return "customer"

        if status == "lost":
            return "lost"

        if score >= cls.HOT_SCORE:
            if value >= 0:
                return "hot"

        if score >= cls.WARM_SCORE:
            return "warm"

        return "cold"

    @classmethod
    def urgency(cls, lead, now=None):
        now = now or datetime.utcnow()

        follow_up = getattr(
            lead,
            "next_follow_up_at",
            None,
        )

        if follow_up:
            if follow_up.date() < now.date():
                return "critical"

            if follow_up.date() == now.date():
                return "high"

        score = cls._score(lead)

        if score >= cls.HOT_SCORE:
            return "high"

        if score >= cls.WARM_SCORE:
            return "medium"

        return "low"

    @classmethod
    def next_best_action(cls, lead, now=None):
        now = now or datetime.utcnow()

        status = cls._status(lead)
        score = cls._score(lead)
        value = cls._value(lead)
        temperature = cls.classify_lead(lead)
        urgency = cls.urgency(
            lead,
            now,
        )

        if status in {
            "won",
            "converted",
        }:
            return {
                "action": "customer_success",
                "label": "Start customer success",
                "reason": "Lead converted successfully.",
                "priority": 10,
            }

        if status == "lost":
            return {
                "action": "reengagement",
                "label": "Schedule re-engagement",
                "reason": "Closed-lost opportunity.",
                "priority": 20,
            }

        if urgency == "critical":
            return {
                "action": "follow_up_now",
                "label": "Follow up immediately",
                "reason": "Follow-up is overdue.",
                "priority": 100,
            }

        if (
            temperature == "hot"
            and value > 0
        ):
            return {
                "action": "close",
                "label": "Move toward close",
                "reason": (
                    "High-intent lead with measurable "
                    "commercial value."
                ),
                "priority": 95,
            }

        if temperature == "hot":
            return {
                "action": "contact_now",
                "label": "Contact immediately",
                "reason": "High-intent lead.",
                "priority": 90,
            }

        if urgency == "high":
            return {
                "action": "follow_up_today",
                "label": "Follow up today",
                "reason": "Scheduled follow-up is due today.",
                "priority": 85,
            }

        if temperature == "warm":
            return {
                "action": "qualify",
                "label": "Qualify opportunity",
                "reason": (
                    "Lead shows meaningful buying intent "
                    "but needs qualification."
                ),
                "priority": 65,
            }

        return {
            "action": "nurture",
            "label": "Add to nurture sequence",
            "reason": "Low current buying intent.",
            "priority": 35,
        }

    @classmethod
    def build_sales_context(cls, lead, now=None):
        now = now or datetime.utcnow()

        score = cls._score(lead)
        value = cls._value(lead)
        temperature = cls.classify_lead(lead)
        urgency = cls.urgency(
            lead,
            now,
        )

        action = cls.next_best_action(
            lead,
            now,
        )

        return {
            "lead_id": lead.id,
            "company_name": (
                lead.company_name
                or "Unnamed company"
            ),
            "email": lead.email or "",
            "status": cls._status(lead),
            "score": score,
            "estimated_value": value,
            "temperature": temperature,
            "urgency": urgency,
            "next_best_action": action,
            "generated_at": now.isoformat(),
        }

    @classmethod
    def rank_leads(cls, leads, limit=20):
        now = datetime.utcnow()

        ranked = []

        for lead in leads:
            context = cls.build_sales_context(
                lead,
                now,
            )

            ranked.append(context)

        ranked.sort(
            key=lambda item: (
                item["next_best_action"]["priority"],
                item["score"],
                item["estimated_value"],
            ),
            reverse=True,
        )

        return ranked[:limit]
