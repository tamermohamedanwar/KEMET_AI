"""
Kemet AI Subscription Service.

Centralizes subscription state and plan operations.
"""


class SubscriptionService:

    @staticmethod
    def get_subscription(organization_id):
        from app.models import Subscription

        return (
            Subscription.query
            .filter_by(organization_id=organization_id)
            .first()
        )

    @staticmethod
    def get_current_plan(organization_id):
        subscription = SubscriptionService.get_subscription(
            organization_id
        )

        if not subscription:
            return "free"

        return subscription.plan or "free"

    @staticmethod
    def is_active(organization_id):
        subscription = SubscriptionService.get_subscription(
            organization_id
        )

        if not subscription:
            return False

        return subscription.status == "active"
