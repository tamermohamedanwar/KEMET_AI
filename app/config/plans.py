from decimal import Decimal


PLAN_DETAILS = {
    "free": {
        "name": "Free",
        "limit": 100,
        "price_usd": Decimal("0.00"),
        "currency": "USD",
        "description": "ابدأ باستخدام Kemet AI واختبر المنصة.",
    },
    "starter": {
        "name": "Starter",
        "limit": 1000,
        "price_usd": Decimal("49.00"),
        "currency": "USD",
        "description": "للأعمال الصغيرة التي تحتاج دعم AI وأتمتة أساسية.",
    },
    "business": {
        "name": "Business",
        "limit": 5000,
        "price_usd": Decimal("99.00"),
        "currency": "USD",
        "description": "للشركات التي تحتاج RAG وأتمتة ودعم AI متقدم.",
    },
    "enterprise": {
        "name": "Enterprise",
        "limit": 50000,
        "price_usd": None,
        "currency": "USD",
        "description": "للفرق والشركات ذات الاستخدام المرتفع والتكاملات المخصصة.",
    },
}


PAID_PLANS = ("starter", "business", "enterprise")


def get_plan(plan):
    plan = (plan or "").strip().lower()

    if plan not in PLAN_DETAILS:
        raise ValueError("Invalid plan")

    return PLAN_DETAILS[plan]


def get_plan_price(plan):
    return get_plan(plan)["price_usd"]


def is_paid_plan(plan):
    return (plan or "").strip().lower() in PAID_PLANS
