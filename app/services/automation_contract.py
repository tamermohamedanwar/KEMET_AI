def action_result(
    action,
    success=True,
    status="completed",
    message=None,
    data=None,
    requires_human=False,
    approval_required=False,
    financial_action_executed=False,
    next_action=None,
):
    return {
        "success": success,
        "action": action,
        "status": status,
        "message": message,
        "data": data or {},
        "requires_human": requires_human,
        "approval_required": approval_required,
        "financial_action_executed": financial_action_executed,
        "next_action": next_action,
    }
