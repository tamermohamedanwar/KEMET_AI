from datetime import datetime, timedelta


class RevenueEventService:

    EVENT_LEAD_HOT = "lead.hot"
    EVENT_LEAD_HIGH_VALUE = "lead.high_value"
    EVENT_LEAD_FOLLOWUP_DUE = "lead.followup_due"
    EVENT_LEAD_FOLLOWUP_OVERDUE = "lead.followup_overdue"
    EVENT_LEAD_STALE = "lead.stale"
    EVENT_LEAD_CONVERTED = "lead.converted"

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
    def build_events(cls, lead, now=None):
        now = now or datetime.utcnow()

        events = []

        status = cls._status(lead)
        score = cls._score(lead)
        value = cls._value(lead)

        base = {
            "lead_id": lead.id,
            "organization_id": (
                lead.organization_id
            ),
            "company_name": (
                lead.company_name
                or "Unnamed company"
            ),
            "estimated_value": value,
            "lead_score": score,
            "created_at": now.isoformat(),
        }

        if status in {
            "won",
            "converted",
        }:
            events.append(
                {
                    "event": cls.EVENT_LEAD_CONVERTED,
                    "data": base,
                }
            )

        if status not in {
            "won",
            "converted",
            "lost",
        }:
            if score >= 75:
                events.append(
                    {
                        "event": cls.EVENT_LEAD_HOT,
                        "data": base,
                    }
                )

            if value >= 1000:
                events.append(
                    {
                        "event": cls.EVENT_LEAD_HIGH_VALUE,
                        "data": base,
                    }
                )

            follow_up = getattr(
                lead,
                "next_follow_up_at",
                None,
            )

            if follow_up:
                if follow_up < now:
                    events.append(
                        {
                            "event": (
                                cls.EVENT_LEAD_FOLLOWUP_OVERDUE
                            ),
                            "data": base,
                        }
                    )
                elif follow_up.date() == now.date():
                    events.append(
                        {
                            "event": (
                                cls.EVENT_LEAD_FOLLOWUP_DUE
                            ),
                            "data": base,
                        }
                    )

            created_at = getattr(
                lead,
                "created_at",
                None,
            )

            if created_at:
                stale_after = created_at + timedelta(
                    days=7
                )

                if (
                    now >= stale_after
                    and score < 45
                ):
                    events.append(
                        {
                            "event": cls.EVENT_LEAD_STALE,
                            "data": base,
                        }
                    )

        return events
