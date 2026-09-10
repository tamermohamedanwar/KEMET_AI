from app import create_app
from app.services.capability_registry import capability_registry


def test_registry_is_versioned_and_active():
    items = capability_registry.catalog()
    assert capability_registry.VERSION == "1.0"
    assert items
    assert all(item["lifecycle"] == "active" for item in items)


def test_capability_contract_contains_governance_and_metrics():
    item = capability_registry.get("kemet.business_insights")
    assert item["registry_version"] == "1.0"
    assert item["version"] == "2.0"
    assert item["metrics"]
    assert item["governance"]["fail_closed"] is True
    assert item["governance"]["external_execution"] is False


def test_unknown_capability_fails_closed():
    assert capability_registry.get("kemet.unknown_action") is None


def test_plan_returns_playbook_without_execution():
    result = capability_registry.plan("kemet.business_insights", {"domain": "marketing"})
    assert result["status"] == "planned"
    assert result["playbook"]["execution"]["mode"] == "governed_sequential"
    assert all(step["policy"]["external_execution"] is False for step in result["playbook"]["steps"])


def test_refund_capability_preserves_approval_gate():
    item = capability_registry.get("kemet.refund_request")
    assert item["governance"]["requires_approval"] is True
    assert item["governance"]["external_execution"] is False


def test_capability_analytics_is_organization_scoped():
    from app.services.capability_analytics import capability_analytics
    app = create_app()
    with app.app_context():
        result = capability_analytics.summary(7)
    assert result["success"] is True
    assert result["organization_id"] == 7
    assert result["governance"]["read_only"] is True
    assert result["governance"]["external_execution"] is False


def test_registry_routes_are_registered():
    app = create_app()
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/bos/capabilities" in routes
    assert "/api/bos/capabilities/<path:capability_id>" in routes
    assert "/api/bos/capabilities/<path:capability_id>/plan" in routes
    assert "/api/bos/capabilities/analytics" in routes


def test_lifecycle_filter_rejects_unknown_value():
    try:
        capability_registry.catalog("unknown")
    except ValueError:
        return
    assert False, "invalid lifecycle must fail closed"
