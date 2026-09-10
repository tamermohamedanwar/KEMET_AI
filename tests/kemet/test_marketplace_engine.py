from app.core.marketplace import MarketplaceEngine, MarketplaceItem

def build_engine():
    return MarketplaceEngine([
        MarketplaceItem(
            item_id="automation.follow_up",
            name="Lead Follow Up",
            category="automation",
            description="Follow up with qualified leads",
            capabilities=("sales", "follow_up"),
            requires_approval=True,
        ),
        MarketplaceItem(
            item_id="agent.sales_advisor",
            name="Sales Advisor",
            category="agent",
            description="Analyze sales opportunities",
            capabilities=("sales", "analysis"),
            requires_approval=True,
        ),
        MarketplaceItem(
            item_id="template.executive_review",
            name="Executive Review",
            category="template",
            description="Executive business review template",
            capabilities=("analytics", "executive"),
            requires_approval=False,
        ),
        MarketplaceItem(
            item_id="integration.whatsapp",
            name="WhatsApp Integration",
            category="integration",
            description="Connect customer messaging",
            capabilities=("whatsapp", "omnichannel"),
            requires_approval=True,
        ),
    ])

def test_marketplace_registry():
    engine = build_engine()
    summary = engine.summary()
    assert summary["total"] == 4
    assert summary["enabled"] == 4
    assert summary["categories"]["automation"] == 1
    assert summary["categories"]["agent"] == 1
    assert summary["categories"]["template"] == 1
    assert summary["categories"]["integration"] == 1

def test_marketplace_search_and_resolve():
    engine = build_engine()
    results = engine.search("sales")
    assert len(results) == 2
    assert engine.resolve("agent.sales_advisor")["category"] == "agent"

def test_marketplace_activation_governance():
    engine = build_engine()
    plan = engine.build_activation_plan("automation.follow_up")
    assert plan["ok"] is True
    assert plan["status"] == "waiting_approval"
    assert plan["requires_approval"] is True
    assert plan["external_execution"] is False
    assert plan["database_mutation"] is False
