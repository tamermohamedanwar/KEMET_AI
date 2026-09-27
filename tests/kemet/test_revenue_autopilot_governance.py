import json

from app import create_app, db
from app.automation.engine import engine
from app.models.automation_execution_ledger import AutomationExecutionLedger
from app.models.automation_outcome import AutomationOutcome
from app.models.execution_evidence import ExecutionEvidence
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

        ledger = AutomationExecutionLedger.query.filter_by(
            organization_id=1,
        ).order_by(AutomationExecutionLedger.id.desc()).first()
        assert ledger is not None
        assert ledger.status == "completed"
        assert ledger.job_id == execution.id
        assert ledger.receipt_json

        outcome = AutomationOutcome.query.filter_by(
            organization_id=1,
            job_id=execution.id,
            workflow_id=str(workflow.id),
            status="completed",
            executed=True,
        ).order_by(AutomationOutcome.id.desc()).first()
        assert outcome is not None
        assert outcome.receipt_json

        evidence = ExecutionEvidence.query.filter_by(
            organization_id=1,
            execution_key=ledger.execution_key,
            stage="runtime.finished",
            status="completed",
        ).order_by(ExecutionEvidence.id.desc()).first()
        assert evidence is not None
        assert evidence.receipt_json

        decision = json.loads(approval.decision_json)
        direct_resume = engine.resume_after_approval(
            approval_id=approval.id,
            execution_id=execution.id,
            workflow_id=workflow.id,
            organization_id=1,
        )
        assert direct_resume["success"] is True
        assert direct_resume["status"] == "deduplicated"
        assert direct_resume["reason"] == "execution_already_completed"
        assert execution.status == "completed"
        assert decision["authorization"]["one_time"] is True

        replay = automation_approval_service.approve(
            approval_id,
            decided_by=1,
        )

        assert replay["success"] is False
        assert "not pending" in replay["message"].lower()

        result_payload = json.loads(execution.output_json or "{}")
        assert result_payload

        evidence_rows = ExecutionEvidence.query.filter_by(
            organization_id=1, execution_key=ledger.execution_key
        ).all()
        for row in evidence_rows:
            db.session.delete(row)
        db.session.delete(outcome)
        db.session.delete(ledger)
        db.session.delete(approval)
        db.session.delete(execution)
        db.session.delete(action)
        db.session.delete(workflow)
        db.session.commit()
