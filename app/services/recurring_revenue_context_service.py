from app.models.subscription import Subscription
from app.services.revenue_pipeline_service import revenue_pipeline_service


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

        commercial_financials = revenue_pipeline_service.dashboard(
            organization_id=int(organization_id)
        )["financials"] if organization_id is not None else {
            "paid_revenue": 0.0,
            "profit_status": "not_verified",
        }
        verified_paid_revenue = float(
            commercial_financials.get("paid_revenue", 0.0) or 0.0
        )

        # Paid commercial revenue is not monthly recurring revenue.
        # No authoritative recurring-billing amount exists in the current model.
        return {
            "active_subscriptions": active,
            "paid_revenue": round(verified_paid_revenue, 2),
            "monthly_recurring_revenue": 0.0,
            "recurring_revenue_status": "not_verified",
            "recurring_revenue_authority": "no_authoritative_recurring_billing_evidence",
            "revenue_authority": "revenue_pipeline_verified_payment_binding",
            "profit_status": commercial_financials.get("profit_status", "not_verified"),
        }
