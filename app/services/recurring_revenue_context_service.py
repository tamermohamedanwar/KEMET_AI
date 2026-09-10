from sqlalchemy import func

from app.models.payment import Payment
from app.models.subscription import Subscription


class RecurringRevenueContextService:

    @classmethod
    def build(cls, organization_id=None):
        subscription_query = Subscription.query

        if organization_id is not None:
            subscription_query = subscription_query.filter(
                Subscription.organization_id == organization_id
            )

        active = subscription_query.filter(
            Subscription.status == "active"
        ).count()

        payment_query = Payment.query.filter(
            Payment.status == "paid"
        )

        if organization_id is not None:
            payment_query = payment_query.filter(
                Payment.organization_id == organization_id
            )

        paid_total = (
            payment_query
            .with_entities(
                func.coalesce(
                    func.sum(Payment.amount),
                    0,
                )
            )
            .scalar()
            or 0
        )

        return {
            "active_subscriptions": active,
            "paid_revenue": round(
                float(paid_total),
                2,
            ),
        }
