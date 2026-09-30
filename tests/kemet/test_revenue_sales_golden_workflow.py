import json
import uuid

from app import create_app, db
from app.automation.engine import engine
from app.models.automation import (
    AutomationAction,
    AutomationApproval,
    AutomationExecution,
    AutomationWorkflow,
)
from app.models.automation_execution_ledger import AutomationExecutionLedger
from app.models.automation_outcome import AutomationOutcome
from app.services.automation_approval_service import automation_approval_service
from app.services.commercial_outcome_trace import commercial_outcome_trace


def test_revenue_sales_golden_workflow_is_commercially_traceable():
    app = create_app()
    workflow = None
    execution = None
    approval = None

    with app.app_context():
        workflow = AutomationWorkflow(
            organization_id=1,
            name=f"Revenue Sales Golden {uuid.uuid4().hex[:8]}",
            description="Commercial trace end-to-end proof.",
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
        assert initial[0]["financial_action_executed"] is False

        approval = db.session.get(AutomationApproval, initial[0]["approval_id"])
        execution = db.session.get(AutomationExecution, initial[0]["execution_id"])
        approved = automation_approval_service.approve(approval.id, decided_by=1)

        assert approved["success"] is True
        assert approved["execution"]["status"] == "completed"
        assert approved["authorization"]["authorized"] is True
        assert approved["authorization"]["one_time"] is True

        execution_key = approved["execution"]["execution_key"]
        trace = commercial_outcome_trace.get(1, execution_key)
        assert trace is not None
        assert trace["organization_id"] == 1
        assert trace["business"]["lead"] == 6
        assert trace["business"]["approval"]["present"] is True
        assert trace["business"]["action"] == "revenue_autopilot_run"
        assert trace["business"]["outcome"] is not None
        assert trace["measurement"]["time_to_outcome_ms"] is not None
        assert trace["measurement"]["causal_claim"] is False
        assert trace["governance"]["tenant_scoped"] is True
        assert trace["governance"]["read_only"] is True

        ledger = AutomationExecutionLedger.query.filter_by(
            organization_id=1,
            execution_key=execution_key,
        ).one()
        outcome = AutomationOutcome.query.filter_by(
            organization_id=1,
            job_id=execution.id,
        ).one()
        assert ledger.status == "completed"
        assert outcome.executed is True
        assert outcome.duration_ms is not None
        assert trace["business"]["revenue"] is None
        assert trace["business"]["roi"] is None
        assert trace["measurement"]["roi_status"] == "not_proven"

        replay = engine.resume_after_approval(
            approval_id=approval.id,
            execution_id=execution.id,
            workflow_id=workflow.id,
            organization_id=1,
        )
        assert replay["status"] == "deduplicated"
        assert AutomationExecutionLedger.query.filter_by(
            organization_id=1,
            execution_key=execution_key,
        ).count() == 1
        assert AutomationOutcome.query.filter_by(
            organization_id=1,
            job_id=execution.id,
        ).count() == 1

        assert commercial_outcome_trace.get(2, execution_key) is None

        db.session.delete(approval)
        db.session.delete(execution)
        db.session.delete(action)
        db.session.delete(workflow)
        db.session.commit()


def test_revenue_sales_golden_workflow_attributes_explicit_recorded_payment():
    app = create_app()
    with app.app_context():
        from app.models.payment import Payment

        payment = Payment(
            organization_id=1,
            plan="business",
            amount=125,
            currency="USD",
            status="paid",
            provider="test",
            provider_transaction_id=f"commercial-{uuid.uuid4().hex}",
        )
        db.session.add(payment)
        db.session.flush()

        workflow = AutomationWorkflow(
            organization_id=1,
            name=f"Revenue Attribution {uuid.uuid4().hex[:8]}",
            description="Recorded payment attribution proof.",
            trigger_type="manual",
            is_active=True,
        )
        db.session.add(workflow)
        db.session.flush()
        action = AutomationAction(
            workflow_id=workflow.id,
            position=1,
            action_type="revenue_autopilot_run",
            config_json=json.dumps({
                "lead_id": 6,
                "recorded_revenue_payment_id": payment.id,
            }),
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
        approval = db.session.get(AutomationApproval, initial[0]["approval_id"])
        execution = db.session.get(AutomationExecution, initial[0]["execution_id"])
        approved = automation_approval_service.approve(approval.id, decided_by=1)

        assert approved["success"] is True
        trace = commercial_outcome_trace.get(1, approved["execution"]["execution_key"])
        assert trace["business"]["revenue"]["amount"] == 125.0
        assert trace["business"]["revenue"]["source"] == "payment_record"
        assert trace["measurement"]["revenue_attribution"]["status"] == "recorded"
        assert trace["measurement"]["causal_claim"] is False
        assert trace["business"]["roi"] is None
        assert trace["measurement"]["roi_proven"] is False

        db.session.delete(approval)
        db.session.delete(execution)
        db.session.delete(action)
        db.session.delete(workflow)
        db.session.delete(payment)
        db.session.commit()
