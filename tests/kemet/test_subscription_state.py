from types import SimpleNamespace
from unittest.mock import patch


def _patch_subscription(subscription):
    query = SimpleNamespace(
        filter_by=lambda **kwargs: query,
        order_by=lambda *args: query,
        first=lambda: subscription,
    )
    return patch("app.models.Subscription", SimpleNamespace(query=query))


def test_missing_subscription_is_free():
    from app.services.subscription_state_service import subscription_state_service
    with _patch_subscription(None):
        result = subscription_state_service.resolve(1)
    assert result["effective_plan"] == "free"
    assert result["reason"] == "no_subscription"
    assert result["active"] is False


def test_active_paid_subscription_keeps_plan():
    from app.services.subscription_state_service import subscription_state_service
    subscription = SimpleNamespace(id=1, organization_id=1, plan="business", status="active")
    with _patch_subscription(subscription):
        result = subscription_state_service.resolve(1)
    assert result["effective_plan"] == "business"
    assert result["active"] is True
    assert result["reason"] == "active"


def test_inactive_subscription_fails_closed_to_free():
    from app.services.subscription_state_service import subscription_state_service
    subscription = SimpleNamespace(id=1, organization_id=1, plan="business", status="inactive")
    with _patch_subscription(subscription):
        result = subscription_state_service.resolve(1)
    assert result["effective_plan"] == "free"
    assert result["active"] is False
    assert result["reason"] == "subscription_inactive"


def test_expired_subscription_fails_closed_to_free():
    from app.services.subscription_state_service import subscription_state_service
    subscription = SimpleNamespace(id=1, organization_id=1, plan="starter", status="expired")
    with _patch_subscription(subscription):
        result = subscription_state_service.resolve(1)
    assert result["effective_plan"] == "free"
    assert result["active"] is False


def test_entitlement_uses_authoritative_effective_plan():
    from app.services.entitlement_service import EntitlementService
    subscription = SimpleNamespace(id=1, organization_id=1, plan="business", status="expired")
    with _patch_subscription(subscription):
        assert EntitlementService.plan(1) == "free"
        assert EntitlementService.feature_enabled(1, "advanced_analytics") is False
