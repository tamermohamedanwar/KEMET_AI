from datetime import datetime, timedelta

class RevenueCommandLeadService:
    PERIODS = {"7d": 7, "30d": 30, "90d": 90}

    @classmethod
    def start_date(cls, period):
        return datetime.utcnow() - timedelta(days=cls.PERIODS.get(period, 30))

    @staticmethod
    def status(lead):
        return (lead.status or "new").strip().lower()

    @staticmethod
    def value(lead):
        try:
            return float(lead.estimated_value or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def score(lead):
        try:
            return max(0, min(int(lead.lead_score or 0), 100))
        except (TypeError, ValueError):
            return 0

    @classmethod
    def next_best_action(cls, lead, now):
        status = cls.status(lead)
        score = cls.score(lead)
        value = cls.value(lead)
        if status in {"won", "converted"}:
            return {"label": "Customer acquired", "type": "success", "priority": 0}
        if status == "lost":
            return {"label": "Closed", "type": "muted", "priority": 0}
        follow_up = getattr(lead, "next_follow_up_at", None)
        if follow_up:
            if follow_up <= now:
                return {"label": "Follow up now", "type": "danger", "priority": 100}
            if follow_up.date() == now.date():
                return {"label": "Follow up today", "type": "warning", "priority": 90}
        if score >= 75 and value > 0:
            return {"label": "Close high-value lead", "type": "success", "priority": 85}
        if score >= 75:
            return {"label": "Contact immediately", "type": "danger", "priority": 80}
        if score >= 45:
            return {"label": "Qualify opportunity", "type": "warning", "priority": 60}
        return {"label": "Nurture lead", "type": "muted", "priority": 30}
