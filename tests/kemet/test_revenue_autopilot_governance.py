import json

from app import create_app, db
from app.automation.engine import engine
from app.models.automation import (
    AutomationAction,
    AutomationApproval,
    AutomationExecution,
    AutomationWorkflow,
)
from app.services.automation_approval_service import automation_approval_service
from app.services.revenue_autopilot_facade import RevenueAutopilotFacade


def test_revenue_autopilot_plan_is_advisory():
    app = create_app()
    with app.app_context():
        result = RevenueAutopilotFacade.plan_for_lead(
            6,
            organization_id=1,
        )

    assert result["success"] is True
    assert result["data"]["status"] == "planned"
    assert result["data"]["plan"]


def test_revenue_autopilot_governed_approval_to_runtime():
    app = create_app()
    workflow = None

    with app.app_context():
        workflow = AutomationWorkflow(
            organization_id=1,
            name="Revenue Autopilot Governance Proof",
            description="Production-path governance proof.",
            trigger_type="manual",
            is_active=True,
        )
        db.session.add(workflow)
        db.session.flush()

        action = AutomationAction(
            workflow_id=workflow.id,
            position=1,
            action_type="revenue_autopilot_run",
            config_json=json.dumps({"lead_id": 6}),
            is_active=True,
        )
        db.session.add(action)
        db.session.commit()

        initial = engine.execute(
            workflow_id=workflow.id,
            event="manual",
            data={"lead_id": 6, "user_id": 1},
            organization_id=1,
        )

        assert initial[0]["status"] == "waiting_approval"
        assert initial[0]["approval_required"] is True
        assert initial[0]["financial_action_executed"] is False

        approval_id = initial[0]["approval_id"]
        execution_id = initial[0]["execution_id"]
        approval = db.session.get(AutomationApproval, approval_id)
        execution = db.session.get(AutomationExecution, execution_id)

        assert approval.execution_id == execution.id
        assert approval.workflow_id == workflow.id
        assert execution.status == "waiting_approval"

        approved = automation_approval_service.approve(
            approval_id,
            decided_by=1,
        )

        assert approved["success"] is True
        assert approved["status"] == "approved"
        assert approved["authorization"]["authorized"] is True
        assert approved["execution"]["status"] == "completed"

        db.session.refresh(approval)
        db.session.refresh(execution)

        assert approval.status == "approved"
        assert execution.status == "completed"

        replay = automation_approval_service.approve(
            approval_id,
            decided_by=1,
        )

        assert replay["success"] is False
        assert "not pending" in replay["message"].lower()

        result_payload = json.loads(execution.output_json or "{}")
        assert result_payload

        db.session.delete(approval)
        db.session.delete(execution)
        db.session.delete(action)
        db.session.delete(workflow)
        db.session.commit()
