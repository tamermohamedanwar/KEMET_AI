from app.core.execution.governed_executor import governed_execution_service


def test_bos_runtime_policy_allows_read_only_operations():
    assert governed_execution_service._policy("business_insights") == "direct_safe"
    assert governed_execution_service._policy("order_tracking") == "direct_safe"
    assert governed_execution_service._policy("lead_scoring") == "direct_safe"
    assert governed_execution_service._policy("churn_detection") == "direct_safe"


def test_bos_runtime_policy_requires_approval_for_side_effects():
    assert governed_execution_service._policy("sales_follow_up") == "approval_required"
    assert governed_execution_service._policy("send_notification") == "approval_required"
    assert governed_execution_service._policy("create_ticket") == "approval_required"
    assert governed_execution_service._policy("refund_request") == "approval_required"


def test_bos_runtime_policy_fails_closed_for_unknown_actions():
    assert governed_execution_service._policy("delete_the_business") == "blocked"


def test_command_center_exposes_outcome_route():
    from app import create_app

    app = create_app()
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/bos/outcome" in routes


def test_command_center_exposes_operating_routes():
    from app import create_app

    app = create_app()
    routes = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/bos/operate" in routes
    assert "/api/bos/approvals/<int:approval_id>/approve" in routes


def test_bos_runtime_plans_approval_without_execution():
    from app import create_app
    from app.services.bos_runtime import BOSRuntime

    app = create_app()
    with app.app_context():
        runtime = BOSRuntime()
        result = runtime.operate("Refund this order", 7, 11)

    assert result["status"] == "waiting_approval"
    assert result["approval_required"] is True
    assert result["executed"] is False
    assert result["approval_id"] is not None
    assert result["workflow_id"] is not None


def test_bos_runtime_plan_exposes_operating_playbook():
    from app.services.bos_runtime import BOSRuntime

    playbook = BOSRuntime().plan("Analyze my business performance")

    assert playbook["status"] == "playbook_ready"
    assert playbook["steps"][0]["action"] == "business_insights"
    assert playbook["steps"][0]["policy"]["fail_closed"] is True
