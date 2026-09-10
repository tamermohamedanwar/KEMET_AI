class RecurringRevenueService:

    @staticmethod
    def calculate(
        active_subscriptions=0,
        monthly_revenue=0.0,
    ):
        active = max(
            int(active_subscriptions or 0),
            0,
        )

        mrr = max(
            float(monthly_revenue or 0),
            0.0,
        )

        arr = mrr * 12

        arpu = (
            mrr / active
            if active
            else 0.0
        )

        return {
            "active_subscriptions": active,
            "mrr": round(mrr, 2),
            "arr": round(arr, 2),
            "arpu": round(arpu, 2),
        }
