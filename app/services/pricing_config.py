"""
Kemet AI Regional Pricing Configuration
Safe pricing layer.
Does not modify production database data.
"""

PLAN_ORDER = (
    "starter",
    "business",
    "enterprise",
)

PLANS = {
    "starter": {
        "name": "Starter",
        "eg": {
            "currency": "EGP",
            "monthly": 49.00,
        },
        "mena": {
            "currency": "USD",
            "monthly": 49.00,
        },
        "international": {
            "currency": "USD",
            "monthly": 49.00,
        },
    },
    "business": {
        "name": "Business",
        "eg": {
            "currency": "EGP",
            "monthly": 99.00,
        },
        "mena": {
            "currency": "USD",
            "monthly": 99.00,
        },
        "international": {
            "currency": "USD",
            "monthly": 99.00,
        },
    },
    "enterprise": {
        "name": "Enterprise",
        "eg": {
            "currency": "EGP",
            "monthly": None,
        },
        "mena": {
            "currency": "USD",
            "monthly": None,
        },
        "international": {
            "currency": "USD",
            "monthly": None,
        },
    },
}

ANNUAL_DISCOUNT = 0.20


def normalize_market(market):
    market = str(market or "").strip().lower()

    if market in {
        "eg",
        "egypt",
        "egyptian",
        "مصر",
    }:
        return "eg"

    if market in {
        "mena",
        "arab",
        "arabic",
        "middle_east",
        "middle-east",
        "gcc",
        "الخليج",
        "العرب",
    }:
        return "mena"

    return "international"


def get_plan(plan):
    plan = str(plan or "").strip().lower()

    if plan not in PLANS:
        raise ValueError(f"Unknown pricing plan: {plan}")

    return PLANS[plan]


def get_price(plan, market="international", billing="monthly"):
    plan_data = get_plan(plan)
    market = normalize_market(market)

    price_data = plan_data[market]
    raw_monthly = price_data["monthly"]

    # Enterprise uses custom pricing.
    if raw_monthly is None:
        return {
            "plan": plan,
            "name": plan_data["name"],
            "market": market,
            "currency": price_data["currency"],
            "monthly": None,
            "amount": None,
            "billing": billing,
            "annual_discount": 0.0,
            "contact_sales": True,
        }

    monthly = float(raw_monthly)

    if billing == "annual":
        amount = round(
            monthly * 12 * (1.0 - ANNUAL_DISCOUNT),
            2,
        )
    else:
        amount = monthly

    return {
        "plan": plan,
        "name": plan_data["name"],
        "market": market,
        "currency": price_data["currency"],
        "monthly": monthly,
        "amount": amount,
        "billing": billing,
        "annual_discount": (
            ANNUAL_DISCOUNT
            if billing == "annual"
            else 0.0
        ),
        "contact_sales": False,
    }


def get_all_prices(market="international"):
    market = normalize_market(market)

    return {
        plan: get_price(plan, market, "monthly")
        for plan in PLAN_ORDER
    }


def get_annual_prices(market="international"):
    market = normalize_market(market)

    return {
        plan: get_price(plan, market, "annual")
        for plan in PLAN_ORDER
    }
