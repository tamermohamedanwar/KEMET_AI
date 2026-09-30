from __future__ import annotations

from typing import Any

from app import db
from app.models.automation import AutomationApproval
from app.models.automation_queue import AutomationQueueJob
from app.core.automation_queue import automation_queue
from app.services.automation_approval_service import automation_approval_service


class AgentApprovalAdapter:
    def prepare(self, run, *, decision: dict[str, Any], actor_id: int | None = None):
        if run is None:
            raise ValueError("agent_run_required")
        if str(run.state) != "approve":
            raise ValueError("agent_run_not_awaiting_approval")

        organization_id = int(run.organization_id)
        plan = dict(run.plan or {})
        steps = list(plan.get("steps") or [])
        if not steps:
            raise ValueError("agent_execution_plan_required")

        step = dict(steps[0])
        action = str(step.get("action") or "").strip()
        if not action:
            raise ValueError("agent_action_required")

        execution_key = str(run.run_id)
        queue_payload = {
            "organization_id": organization_id,
            "job_key": execution_key,
            "workflow_id": f"agent:{run.run_id}",
            "execution_id": execution_key,
            "idempotency_key": execution_key,
            "workflow_state": "waiting_approval",
            "execution_key": execution_key,
            "plan_hash": str(plan.get("plan_hash") or ""),
            "decision_hash": str((decision or {}).get("decision_hash") or ""),
            "payload": {
                "agent_run_id": run.run_id,
                "instruction": run.instruction,
                "organization_id": organization_id,
                "execution_plan": plan,
                "decision": decision,
                "actor_id": actor_id,
                "runtime": "kemet_agent_runtime",
                "runtime_version": "1.1",
                "canonical_execution_runtime": True,
                "external_execution_authority": False,
            },
        }

        queued = automation_queue.enqueue(queue_payload)
        job_id = int(queued["job_id"])

        approval = automation_approval_service.create(
            organization_id=organization_id,
            action_type=action,
            reason=f"Agent Runtime human approval: {run.instruction}",
            request_data={
                "action": action,
                "parameters": dict(step.get("parameters") or {}),
                "data": dict(step.get("parameters") or {}),
                "queue_job_id": job_id,
                "agent_run_id": run.run_id,
                "instruction": run.instruction,
                "plan": plan,
                "decision": decision,
            },
            requested_by=actor_id,
        )

        if not approval.get("success"):
            job = db.session.get(AutomationQueueJob, job_id)
            if job is not None:
                db.session.delete(job)
                db.session.commit()
            raise ValueError(approval.get("message") or "agent_approval_creation_failed")

        approval_id = int(approval["approval_id"])
        return {
            "approval_id": approval_id,
            "job_id": job_id,
            "job_key": execution_key,
            "organization_id": organization_id,
            "workflow_state": "waiting_approval",
            "approval_status": "pending",
            "action": action,
        }


agent_approval_adapter = AgentApprovalAdapter()
