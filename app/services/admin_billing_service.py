"""
Kemet AI Admin Billing Service.
"""

from app.models import Subscription, Payment


class AdminBillingService:

    @staticmethod
    def get_subscription_summary():
        subscriptions = Subscription.query.all()

        return {
            "total": len(subscriptions),
            "active": sum(
                1
                for item in subscriptions
                if item.status == "active"
            ),
            "inactive": sum(
                1
                for item in subscriptions
                if item.status != "active"
            ),
        }

    @staticmethod
    def get_payment_summary():
        payments = Payment.query.all()

        return {
            "total": len(payments),
            "paid": sum(
                1
                for item in payments
                if item.status == "paid"
            ),
            "refunded": sum(
                1
                for item in payments
                if item.status == "refunded"
            ),
        }
