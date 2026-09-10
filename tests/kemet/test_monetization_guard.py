from app.services.monetization_guard import monetization_guard


def test_monetization_guard_requires_org():
    result = monetization_guard.feature(None, "crm")
    assert result["allowed"] is False
    assert result["reason"] == "organization_required"


def test_monetization_guard_blocks_unentitled_feature(monkeypatch):
    monkeypatch.setattr(
        "app.services.monetization_guard.EntitlementService.require_feature",
        lambda org, feature: {
            "allowed": False,
            "plan": "free",
            "feature": feature,
            "reason": "feature_not_available_on_plan",
        },
    )
    result = monetization_guard.feature(1, "automation")
    assert result["allowed"] is False
    assert result["reason"] == "feature_not_available_on_plan"


def test_monetization_guard_blocks_usage(monkeypatch):
    monkeypatch.setattr(
        "app.services.monetization_guard.EntitlementService.require_feature",
        lambda org, feature: {
            "allowed": True,
            "plan": "starter",
            "feature": feature,
            "reason": "feature_enabled",
        },
    )
    monkeypatch.setattr(
        "app.services.monetization_guard.EntitlementService.usage",
        lambda org: {
            "allowed": False,
            "plan": "starter",
            "limit": 1000,
            "used": 1000,
            "remaining": 0,
        },
    )
    result = monetization_guard.feature(1, "automation", require_usage=True)
    assert result["allowed"] is False
    assert result["reason"] == "usage_limit_reached"


def test_monetization_guard_is_non_executing():
    result = monetization_guard.feature(1, "crm")
    assert result["governance"]["external_execution"] is False
    assert result["governance"]["database_mutation"] is False
    assert result["governance"]["payment_execution"] is False
    assert result["governance"]["auto_execute"] is False
