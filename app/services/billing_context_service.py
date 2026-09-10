class BillingContextService:
    @staticmethod
    def build_context(
        plan,
        organization_id=None,
        payment_provider="paymob",
    ):
        from decimal import Decimal

        from app.services.payment_service import PLAN_PRICES
        from app.services.exchange_rate_service import convert_usd_to_egp

        if isinstance(plan, dict):
            plan_name = plan.get("name")
            plan_slug = plan.get("slug")
            plan_id = plan.get("id")
        else:
            plan_name = getattr(plan, "name", None)
            plan_slug = getattr(plan, "slug", None)
            plan_id = getattr(plan, "id", None)

        if not plan_slug:
            raise ValueError("Billing plan slug is required")

        plan_slug = str(plan_slug).lower()

        if plan_slug not in PLAN_PRICES:
            raise ValueError(f"Unknown billing plan: {plan_slug}")

        price_usd = PLAN_PRICES[plan_slug]

        # Enterprise is custom-priced and must never enter
        # numeric payment preparation.
        if price_usd is None:
            payment_intent = {
                "plan_id": plan_id,
                "plan_slug": plan_slug,
                "plan_name": plan_name,
                "amount": None,
                "amount_usd": None,
                "amount_egp": None,
                "currency": "EGP",
                "currency_usd": "USD",
                "organization_id": organization_id,
                "provider": payment_provider,
                "status": "contact_sales",
                "executed": False,
                "contact_sales": True,
            }

            return {
                "plan": {
                    "id": plan_id,
                    "name": plan_name,
                    "slug": plan_slug,
                    "price": None,
                    "price_usd": None,
                    "price_egp": None,
                    "contact_sales": True,
                },
                "organization_id": organization_id,
                "payment_provider": payment_provider,
                "payment_ready": False,
                "payment_executed": False,
                "payment_intent": payment_intent,
                "contact_sales": True,
            }

        price_usd = Decimal(str(price_usd))
        fx = convert_usd_to_egp(price_usd)
        price_egp = fx["egp"]

        payment_intent = {
            "plan_id": plan_id,
            "plan_slug": plan_slug,
            "plan_name": plan_name,
            "amount": price_egp,
            "amount_usd": price_usd,
            "amount_egp": price_egp,
            "currency": "EGP",
            "currency_usd": "USD",
            "organization_id": organization_id,
            "provider": payment_provider,
            "status": "preview",
            "executed": False,
            "contact_sales": False,
            "exchange_rate": fx["rate"],
            "exchange_rate_source": fx["source"],
            "exchange_rate_date": fx["provider_date"],
            "exchange_rate_fallback": fx["fallback"],
        }

        return {
            "plan": {
                "id": plan_id,
                "name": plan_name,
                "slug": plan_slug,
                "price": price_egp,
                "price_usd": price_usd,
                "price_egp": price_egp,
                "contact_sales": False,
            },
            "organization_id": organization_id,
            "payment_provider": payment_provider,
            "payment_ready": True,
            "payment_executed": False,
            "payment_intent": payment_intent,
            "contact_sales": False,
        }
