from app.services.corporate_force_card import corporate_force_card
from wsgi import application


def _client_as_admin():
    application.config["WTF_CSRF_ENABLED"] = False
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "1"
        session["_fresh"] = True
    return client


def test_corporate_force_card_is_role_task_result_bound():
    with application.app_context():
        card = corporate_force_card.build(1, "ai_sales_manager")
    assert card["schema"] == "kemet.corporate_force_card.v3"
    assert card["identity"]["id"] == "ai_sales_manager"
    assert card["role"]["name"] == "sales_manager"
    assert "sales_follow_up" in card["tasks"]["assignment_contract"]["accepted_actions"]
    assert "qualified_leads" in card["results"]["expected_metrics"]
    assert card["governance"]["execution_authority"] is False
    assert card["governance"]["mcp"] is False
    assert card["card_digest"]


def test_corporate_force_card_fails_closed_for_unknown_workforce():
    with application.app_context():
        card = corporate_force_card.build(1, "unknown_agent")
    assert card["status"] == "BLOCKED"
    assert card["error"] == "workforce_not_found"
    assert card["governance"]["fail_closed"] is True


def test_corporate_force_team_card_is_tenant_scoped():
    with application.app_context():
        team = corporate_force_card.build_team(1)
    assert team["organization_id"] == 1
    assert team["card_count"] > 0
    assert team["ready_count"] == team["card_count"]
    assert team["governance"]["tenant_scoped"] is True
    assert team["team_digest"]


def test_corporate_force_routes_are_read_only_cards():
    client = _client_as_admin()
    team_response = client.get("/api/workforce/corporate-force")
    member_response = client.get("/api/workforce/ai_sales_manager/card")
    assert team_response.status_code == 200
    assert member_response.status_code == 200
    assert team_response.get_json()["card_count"] > 0
    assert member_response.get_json()["identity"]["id"] == "ai_sales_manager"


def test_runtime_task_keeps_bound_input_for_result_traceability():
    from app.workforce.runtime import workforce_runtime
    created = workforce_runtime.create_task(
        workforce_id="ai_sales_manager",
        action="lead_scoring",
        organization_id=1,
        data={"trace_marker": "corporate-force-test"},
        user_id=1,
    )
    assert created["success"] is True
    task = workforce_runtime.get_task(created["task"]["id"])
    assert task["data"]["trace_marker"] == "corporate-force-test"
    workforce_runtime._tasks.pop(task["id"], None)
