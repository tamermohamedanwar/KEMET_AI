from app import create_app
from app.automation.orchestrator import orchestrator
from app.automation.playbook_engine import playbook_engine
from app.services.business_outcome_service import BusinessOutcomeService


def test_playbook_catalog_is_versioned():
    assert playbook_engine.VERSION == "2.0"
    assert len(playbook_engine.catalog()) >= 10


def test_catalog_contains_core_business_domains():
    domains = {item["domain"] for item in playbook_engine.catalog()}
    assert {"sales", "customer", "finance", "operations", "support", "revenue"}.issubset(domains)


def test_playbook_definition_is_reusable():
    definition = playbook_engine.get_definition("lead_scoring")
    assert definition["name"] == "Revenue Pipeline Accelerator"
    assert definition["domain"] == "sales"
    assert definition["version"] == "2.0"


def test_unknown_playbook_is_not_executable():
    assert playbook_engine.get_definition("delete_business") is None


def test_marketing_command_uses_safe_read_only_action():
    plan = orchestrator.plan("Analyze marketing performance")
    assert plan["action"] == "business_insights"
    assert plan["parameters"]["domain"] == "marketing"
    assert plan["requires_approval"] is False


def test_finance_command_uses_safe_read_only_action():
    plan = orchestrator.plan("Analyze financial performance")
    assert plan["action"] == "business_insights"
    assert plan["parameters"]["domain"] == "finance"


def test_contracting_command_uses_safe_read_only_action():
    plan = orchestrator.plan("Analyze contracts")
    assert plan["action"] == "business_insights"
    assert plan["parameters"]["domain"] == "contracting"


def test_real_estate_command_uses_safe_read_only_action():
    plan = orchestrator.plan("Analyze real estate performance")
    assert plan["action"] == "business_insights"
    assert plan["parameters"]["domain"] == "real_estate"


def test_media_and_sports_command_uses_safe_read_only_action():
    plan = orchestrator.plan("Analyze media performance")
    assert plan["action"] == "business_insights"
    assert plan["parameters"]["domain"] == "media_sports"


def test_industry_command_uses_safe_read_only_action():
    plan = orchestrator.plan("Analyze industry performance")
    assert plan["action"] == "business_insights"
    assert plan["parameters"]["domain"] == "industry"


def test_comparison_command_uses_safe_read_only_action():
    plan = orchestrator.plan("Compare businesses")
    assert plan["action"] == "business_insights"
    assert plan["parameters"]["domain"] == "comparison"


def test_domain_plan_remains_non_external():
    playbook = playbook_engine.build(orchestrator.plan("Analyze marketing performance"))
    assert playbook["execution"]["mode"] == "governed_sequential"
    assert all(step["policy"]["external_execution"] is False for step in playbook["steps"])


def test_refund_playbook_requires_approval():
    playbook = playbook_engine.build(orchestrator.plan("Refund this order"))
    assert playbook["requires_approval"] is True
    assert playbook["risk"] == "high"
    assert playbook["steps"][0]["policy"]["fail_closed"] is True


def test_sales_playbook_preserves_downstream_governance():
    playbook = playbook_engine.build(orchestrator.plan("Find my hottest leads"))
    assert len(playbook["steps"]) == 3
    assert playbook["steps"][0]["action"] == "lead_scoring"
    assert playbook["steps"][1]["depends_on"] == ["step_1"]
    assert playbook["steps"][2]["depends_on"] == ["step_2"]


def test_outcome_actions_include_playbook_metadata():
    app = create_app()
    with app.app_context():
        result = BusinessOutcomeService.build(7)
    for action in result["next_best_actions"]:
        if action.get("action"):
            assert "playbook" in action


def test_playbook_routes_are_registered():
    app = create_app()
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/bos/playbooks" in routes
    assert "/api/bos/playbooks/<action>" in routes


def test_catalog_is_advisory():
    app = create_app()
    with app.test_request_context():
        definition = playbook_engine.get_definition("sales_follow_up")
    assert definition["domain"] == "sales"
