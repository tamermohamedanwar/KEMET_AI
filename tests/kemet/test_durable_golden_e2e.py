import json
import uuid

from app.models.automation import AutomationExecution, AutomationWorkflow

from wsgi import application
from app import db
from app.models.organization import Organization
from app.models.subscription import Subscription
from app.models.automation_queue import AutomationQueueJob
from app.core.automation_queue import automation_queue
from app.core.governed_worker import GovernedWorker
from app.core.golden_workflow_trace import golden_workflow_trace
from app.services.automation_approval_service import automation_approval_service


def test_real_durable_queue_worker_golden_e2e():
    with application.app_context():
        token = uuid.uuid4().hex[:12]
        org = Organization(name=f"Durable E2E {token}", slug=f"durable-e2e-{token}")
        db.session.add(org)
        db.session.flush()
        db.session.add(Subscription(organization_id=org.id, plan="business", status="active"))
        db.session.commit()
        workflow = AutomationWorkflow(organization_id=org.id, name=f"Durable E2E Workflow {token}",
            trigger_type="manual_command", is_active=True)
        db.session.add(workflow)
        db.session.flush()
        execution = AutomationExecution(workflow_id=workflow.id, trigger_type="manual_command",
            status="waiting_approval")
        db.session.add(execution)
        db.session.flush()
        execution_key = f"e2e-key-{token}"
        queued = automation_queue.enqueue({"organization_id": org.id, "job_key": execution_key,
            "execution_id": execution.id, "idempotency_key": execution_key,
            "workflow_id": workflow.id, "workflow_state": "waiting_approval", "priority": 0})
        approval = automation_approval_service.create(organization_id=org.id, action_type="check_order",
            reason="durable golden e2e", request_data={"action": "check_order",
            "parameters": {"order_id": f"E2E-{token}"}}, workflow_id=workflow.id,
            execution_id=execution.id, requested_by=1)
        assert approval["success"] is True
        approved = automation_approval_service.approve(approval["approval_id"], decided_by=1)
        assert approved["success"] is True, approved
        result = GovernedWorker().process_one(worker_id=f"e2e-worker-{token}",
            plan_resolver=lambda payload: (_ for _ in ()).throw(AssertionError("durable resolver used")))
        job = db.session.get(AutomationQueueJob, queued["job_id"])
        assert result["status"] == "completed", result
        assert result["executed"] is True
        assert job.workflow_state == "completed"
        assert job.status == "completed"
        payload = json.loads(job.payload_json)
        trace = golden_workflow_trace.assert_terminal_completed(organization_id=org.id,
            job_id=job.id, execution_key=execution_key, plan_hash=payload["authorization"]["plan_hash"])
        assert trace["ok"] is True
