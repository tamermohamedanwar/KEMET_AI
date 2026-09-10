from app.core.execution import ExecutionService


def test_execution_validation():
    result = ExecutionService.validate_request(
        action="create_ticket",
        parameters={"title": "Customer issue"},
    )

    assert result["success"] is True
    assert result["status"] == "ready"


def test_execution_requires_approval():
    result = ExecutionService.validate_request(
        action="send_notification",
        parameters={"message": "Hello"},
        requires_approval=True,
    )

    assert result["success"] is True
    assert result["status"] == "waiting_approval"
    assert result["requires_approval"] is True


def test_execution_plan_is_safe():
    result = ExecutionService.build_execution_plan(
        action="send_notification",
        parameters={"message": "Hello"},
        requires_approval=True,
    )

    assert result["success"] is True
    assert result["engine"] == "kemet_execution"
    assert result["external_execution"] is False
    assert result["database_mutation"] is False
