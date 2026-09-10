"""
Kemet AI Billing Service.

Central billing orchestration layer.
Provider-specific payment operations remain isolated
inside payment_service.py.
"""


class BillingService:

    @staticmethod
    def get_plan_prices():
        from app.services.payment_service import PLAN_PRICES
        return dict(PLAN_PRICES)

    @staticmethod
    def get_available_plans():
        from app.services.packaging_service import packaging_service
        return packaging_service.catalog()
