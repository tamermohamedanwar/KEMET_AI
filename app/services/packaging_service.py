"""Global Kemet packaging policy."""

from app.config.plans import PLAN_DETAILS


PACKAGING = {
    "free": {
        "position": "Explore Kemet",
        "target": "individuals_and_early_teams",
        "billing_interval": "monthly",
        "usage_unit": "ai_requests",
        "overage": False,
    },
    "starter": {
        "position": "Run core business workflows",
        "target": "small_businesses",
        "billing_interval": "monthly",
        "usage_unit": "ai_requests",
        "overage": False,
    },
    "business": {
        "position": "Operate and optimize the business",
        "target": "growing_companies",
        "billing_interval": "monthly",
        "usage_unit": "ai_requests",
        "overage": False,
    },
    "enterprise": {
        "position": "Govern Kemet at scale",
        "target": "enterprise_and_multi_team",
        "billing_interval": "custom",
        "usage_unit": "ai_requests",
        "overage": "contracted",
    },
}


class PackagingService:
    VERSION = "1.0"

    @classmethod
    def catalog(cls):
        result = []
        for slug, details in PLAN_DETAILS.items():
            package = dict(PACKAGING.get(slug, {}))
            package.update({
                "id": slug,
                "slug": slug,
                "name": details.get("name", slug.title()),
                "price_usd": details.get("price_usd"),
                "currency": details.get("currency", "USD"),
                "limit": details.get("limit"),
                "description": details.get("description", ""),
                "contact_sales": details.get("price_usd") is None,
            })
            result.append(package)
        return result

    @classmethod
    def get(cls, plan):
        key = str(plan or "").strip().lower()
        if key not in PLAN_DETAILS:
            raise ValueError("Invalid plan")
        return next(item for item in cls.catalog() if item["slug"] == key)


packaging_service = PackagingService()
