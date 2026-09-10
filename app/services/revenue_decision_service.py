from datetime import datetime


class RevenueDecisionService:

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
            return max(
                float(lead.estimated_value or 0),
                0.0,
            )
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _status(lead):
        return (
            lead.status or "new"
        ).strip().lower()

    @classmethod
    def decide(cls, lead, now=None):
        now = now or datetime.utcnow()

        status = cls._status(lead)
        score = cls._score(lead)
        value = cls._value(lead)

        if status in {
            "won",
            "converted",
            "lost",
        }:
            return {
                "priority": "none",
                "action": "monitor",
                "reason": "Lead is already closed.",
                "score": score,
                "estimated_value": value,
            }

        follow_up = getattr(
            lead,
            "next_follow_up_at",
            None,
        )

        if follow_up and follow_up < now:
            return {
                "priority": "critical",
                "action": "follow_up_now",
                "reason": "Follow-up is overdue.",
                "score": score,
                "estimated_value": value,
            }

        if score >= 80 and value >= 1000:
            return {
                "priority": "critical",
                "action": "sales_contact",
                "reason": "High-intent high-value opportunity.",
                "score": score,
                "estimated_value": value,
            }

        if score >= 75:
            return {
                "priority": "high",
                "action": "sales_follow_up",
                "reason": "Hot lead requires immediate attention.",
                "score": score,
                "estimated_value": value,
            }

        if value >= 5000:
            return {
                "priority": "high",
                "action": "high_value_follow_up",
                "reason": "High-value opportunity.",
                "score": score,
                "estimated_value": value,
            }

        if score >= 45:
            return {
                "priority": "medium",
                "action": "nurture",
                "reason": "Warm opportunity should be nurtured.",
                "score": score,
                "estimated_value": value,
            }

        return {
            "priority": "low",
            "action": "qualification",
            "reason": "Lead needs qualification before sales effort.",
            "score": score,
            "estimated_value": value,
        }

    @classmethod
    def rank(cls, leads):
        ranked = []

        priority_weight = {
            "critical": 4,
            "high": 3,
            "medium": 2,
            "low": 1,
            "none": 0,
        }

        for lead in list(leads or []):
            decision = cls.decide(lead)

            weighted_score = (
                priority_weight.get(
                    decision["priority"],
                    0,
                ) * 10000
                + decision["score"] * 100
                + min(
                    decision["estimated_value"],
                    999999,
                )
            )

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
