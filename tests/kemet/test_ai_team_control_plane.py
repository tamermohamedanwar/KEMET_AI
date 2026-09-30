from app.services.ai_team_control_plane import ai_team_control_plane


def test_team_snapshot_is_tenant_bound_and_non_executing():
    result = ai_team_control_plane.team_snapshot(1)
    assert result["organization_id"] == 1
    assert result["member_count"] > 0
    assert result["governance"]["execution_authority"] is False
    assert result["governance"]["mcp"] is False


def test_assignment_preview_binds_existing_workforce_and_plan():
    result = ai_team_control_plane.assignment_preview(
        1,
        "ai_sales_manager",
        "Analyze the sales pipeline and prepare a follow-up plan",
        issue_id="SALES-1",
    )
    assert result["action_allowed"] is False
    assert result["plan_hash"]
    assert result["assignment_digest"]
    assert result["governance"]["human_approval_required"] is True


def test_approval_action_remains_governed():
    result = ai_team_control_plane.assignment_preview(
        1,
        "ai_store_manager",
        "Process a refund request for the customer",
        action="refund_request",
    )
    assert result["action_allowed"] is False
    assert result["requires_approval"] is True
    assert result["assignment_state"] == "READY_FOR_APPROVAL"


def test_mentions_and_schedules_are_proposals_not_execution():
    mention = ai_team_control_plane.mention_preview(
        1,
        "@ai_sales_manager",
        "Review today's qualified leads",
    )
    schedule = ai_team_control_plane.schedule_preview(
        1,
        "ai_sales_manager",
        "Review today's qualified leads",
        "0 9 * * 1-5",
    )
    assert mention["assignment_digest"]
    assert schedule["status"] == "SCHEDULE_PROPOSAL"
    assert schedule["schedule_digest"]
    assert schedule["governance"]["auto_execute"] is False


def test_unknown_agent_fails_closed():
    result = ai_team_control_plane.assignment_preview(1, "unknown_agent", "Do work")
    assert result["status"] == "BLOCKED"
    assert result["error"] == "workforce_not_found"
