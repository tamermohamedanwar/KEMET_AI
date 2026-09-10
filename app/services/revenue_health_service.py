class RevenueHealthService:

    @classmethod
    def calculate(cls, sales, payments, followups):
        total_leads = int(
            sales.get("total_leads", 0)
        )

        won_leads = int(
            sales.get("won_leads", 0)
        )

        pipeline = float(
            sales.get("pipeline_value", 0)
        )

        weighted = float(
            sales.get("weighted_pipeline", 0)
        )

        paid = float(
            payments.get("paid_amount", 0)
        )

        overdue = int(
            followups.get("overdue", 0)
        )

        score = 0

        if total_leads > 0:
            score += 15

        if won_leads > 0:
            score += 25

        if pipeline > 0:
            score += 20

        if weighted > 0:
            score += 20

        if paid > 0:
            score += 20

        if overdue > 5:
            score -= 10
        elif overdue > 0:
            score -= 5

        score = max(
            0,
            min(score, 100),
        )

        if score >= 80:
            label = "excellent"
        elif score >= 60:
            label = "healthy"
        elif score >= 40:
            label = "attention"
        else:
            label = "critical"

        return {
            "score": score,
            "label": label,
            "pipeline": round(pipeline, 2),
            "weighted_pipeline": round(
                weighted,
                2,
            ),
            "paid_revenue": round(
                paid,
                2,
            ),
            "overdue_followups": overdue,
        }
