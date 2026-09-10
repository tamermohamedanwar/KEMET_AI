from decimal import Decimal

from app.services.packaging_service import PackagingService


def test_global_packaging_has_all_plans():
    catalog = PackagingService.catalog()
    assert {item["slug"] for item in catalog} == {
        "free", "starter", "business", "enterprise"
    }


def test_paid_packages_have_explicit_commercial_metadata():
    starter = PackagingService.get("starter")
    business = PackagingService.get("business")
    enterprise = PackagingService.get("enterprise")

    assert starter["price_usd"] == Decimal("49.00")
    assert business["price_usd"] == Decimal("99.00")
    assert enterprise["contact_sales"] is True
    assert starter["billing_interval"] == "monthly"
    assert business["usage_unit"] == "ai_requests"


def test_packaging_is_read_only():
    item = PackagingService.get("business")
    assert item["slug"] == "business"
    assert item["overage"] is False
