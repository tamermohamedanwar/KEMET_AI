from app.services.ai_usage_service import check_limit


PLAN_FEATURES = {
    "free": {
        "automation": False,
        "advanced_automation": False,
        "ai_sales": False,
        "customer_retention": False,
        "revenue_intelligence": False,
    },
    "starter": {
        "automation": True,
        "advanced_automation": False,
        "ai_sales": False,
        "customer_retention": False,
        "revenue_intelligence": False,
    },
    "business": {
        "automation": True,
        "advanced_automation": True,
        "ai_sales": True,
        "customer_retention": True,
        "revenue_intelligence": True,
    },
    "enterprise": {
        "automation": True,
        "advanced_automation": True,
        "ai_sales": True,
        "customer_retention": True,
        "revenue_intelligence": True,
    },
}


def get_plan_features(organization_id):
    usage = check_limit(organization_id)
    plan = usage.get("plan", "free")

    return {
        "plan": plan,
        "features": PLAN_FEATURES.get(
            plan,
            PLAN_FEATURES["free"],
        ),
    }


def feature_allowed(organization_id, feature):
    result = get_plan_features(organization_id)
    return bool(
        result["features"].get(feature, False)
    )


def revenue_access(organization_id, feature):
    result = get_plan_features(organization_id)
    allowed = bool(
        result["features"].get(feature, False)
    )

    return {
        "allowed": allowed,
        "plan": result["plan"],
        "feature": feature,
        "upgrade_required": not allowed,
    }
