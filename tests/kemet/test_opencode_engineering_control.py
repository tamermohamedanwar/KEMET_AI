from app.services.opencode_engineering_control import opencode_engineering_control
from wsgi import application


def test_role_catalog_is_governed():
    catalog = opencode_engineering_control.role_catalog()
    assert catalog["schema"] == "kemet.opencode_engineering_control.v1"
    assert catalog["roles"]["plan"]["permissions"]["edit"] == "deny"
    assert catalog["roles"]["review"]["permissions"]["edit"] == "deny"
    assert catalog["governance"]["mcp"] is False
    assert catalog["catalog_digest"]


def test_plan_is_reviewable_and_not_execution_authority():
    plan = opencode_engineering_control.plan("Improve command center UX", 1)
    assert [step["role"] for step in plan["workflow"]] == ["plan", "build", "review", "test_runner"]
    assert "before_canonical_execution" in plan["approval_points"]
    assert plan["governance"]["execution_authority"] is False


def test_unknown_engineering_role_fails_closed():
    result = opencode_engineering_control.assignment_preview("x", 1, "unknown")
    assert result["status"] == "BLOCKED"
    assert result["error"] == "engineering_role_not_found"


def test_build_requires_review_for_edits_and_commands():
    result = opencode_engineering_control.assignment_preview("fix tests", 1, "build")
    assert result["status"] == "READY_FOR_REVIEW"
    assert result["permissions"]["edit"] == "ask"
    assert result["permissions"]["bash"] == "ask"
    assert result["authority"] == "advisory_only"


def test_plan_role_is_read_only():
    result = opencode_engineering_control.assignment_preview("analyze architecture", 1, "plan")
    assert result["permissions"]["edit"] == "deny"
    assert result["permissions"]["bash"] == "ask"


def test_routes_are_read_only_engineering_control():
    application.config["WTF_CSRF_ENABLED"] = False
    client = application.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = "1"
        session["_fresh"] = True
    response = client.get("/api/workforce/engineering/opencode")
    assert response.status_code == 200
    assert response.get_json()["roles"]["review"]["permissions"]["edit"] == "deny"
