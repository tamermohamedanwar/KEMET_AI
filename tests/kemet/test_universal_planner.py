from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_planner_returns_governed_plan_metadata():
    from app.automation.orchestrator import orchestrator

    plan = orchestrator.plan("Analyze my business performance")

    assert plan["status"] == "planned"
    assert plan["action"] == "business_insights"
    assert plan["risk"] == "low"
    assert plan["expected_result"]
    assert plan["requires_approval"] is False


def test_planner_marks_financial_action_for_approval():
    from app.automation.orchestrator import orchestrator

    plan = orchestrator.plan("I need a refund")

    assert plan["action"] == "refund_request"
    assert plan["requires_approval"] is True
    assert plan["risk"] == "high"
    assert plan["approval_reason"]


def test_plan_route_exists():
    from wsgi import application

    routes = {str(rule) for rule in application.url_map.iter_rules()}
    assert "/api/bos/plan" in routes


def test_planner_marks_outbound_follow_up_as_high_risk():
    from app.automation.orchestrator import orchestrator

    plan = orchestrator.plan("Follow up with customer 42")

    assert plan["action"] == "sales_follow_up"
    assert plan["risk"] == "high"


def test_planner_rejects_unknown_commands():
    from app.automation.orchestrator import orchestrator

    try:
        orchestrator.plan("do something completely unsupported")
    except ValueError as exc:
        assert "safely map" in str(exc)
    else:
        raise AssertionError("Unsupported command was accepted")
