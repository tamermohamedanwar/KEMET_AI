import json
from datetime import datetime

from app import db
from app.models.automation import (
    AutomationApproval,
    AutomationExecution,
)
from app.models.automation_queue import AutomationQueueJob
from app.core.workflow_runtime import WorkflowState
from app.core.workflow_coordinator import workflow_coordinator


class AutomationApprovalService:

    def create(
        self,
        organization_id,
        action_type,
        reason,
        request_data=None,
        workflow_id=None,
        execution_id=None,
        requested_by=None,
    ):
        try:
            organization_id = int(organization_id)
            workflow_id = int(workflow_id) if workflow_id is not None else None
            execution_id = int(execution_id) if execution_id is not None else None
            requested_by = int(requested_by) if requested_by is not None else None
        except (TypeError, ValueError):
            return {
                "success": False,
                "status": "blocked",
                "message": "Approval identity fields must use canonical integer database identifiers.",
                "error": "approval_identity_invalid",
            }

        approval = AutomationApproval(
            organization_id=organization_id,
            workflow_id=workflow_id,
            execution_id=execution_id,
            action_type=action_type,
            status="pending",
            reason=reason,
            request_json=json.dumps(
                request_data or {},
                ensure_ascii=False,
                default=str,
            ),
            requested_by=requested_by,
        )

        db.session.add(approval)
        db.session.flush()

        if execution_id is not None:
            job = AutomationQueueJob.query.filter_by(
                organization_id=int(organization_id), execution_id=str(execution_id)
            ).order_by(AutomationQueueJob.id.desc()).first()
            if job is not None and job.workflow_state != WorkflowState.WAITING_APPROVAL:
                workflow_coordinator.transition_job(
                    job.id, WorkflowState.WAITING_APPROVAL,
                    reason="human_approval_requested",
                    actor="approval_service",
                    metadata={"approval_id": approval.id},
                    commit=False,
                )

        db.session.commit()

        return {
            "success": True,
            "approval_id": approval.id,
            "status": approval.status,
            "action": action_type,
            "approval_required": True,
            "message": "Human approval required.",
        }

    def approve(self, approval_id, decided_by=None):
        approval = db.session.get(AutomationApproval, approval_id)

        if approval is None:
            return {
                "success": False,
                "message": "Approval request not found.",
            }

        if approval.status != "pending":
            return {
                "success": False,
                "message": "Approval request is not pending.",
                "status": approval.status,
            }

        request_data = {}
        if approval.request_json:
            try:
                request_data = json.loads(approval.request_json)
            except Exception:
                request_data = {}

        action_type = request_data.get("action") or approval.action_type
        parameters = dict(request_data.get("parameters") or {})
        data = request_data.get("data") or {}

        # Build the exact execution parameters before authorization.
        # Runtime later reconstructs these parameters and may inject
        # the server-side approval marker. The marker is excluded from
        # canonical hashing, so the signed plan remains stable.
        execution_parameters = dict(parameters)

        for key, value in data.items():
            execution_parameters.setdefault(key, value)

        # Build the exact execution plan before execution.
        plan = {
            "request": "automation_approval",
            "decision": "approved",
            "context": {
                "organization_id": approval.organization_id,
                "workflow_id": approval.workflow_id,
                "execution_id": approval.execution_id,
                "approval_id": approval.id,
                "action_id": request_data.get("action_id"),
            },
            "action": action_type,
            "status": "approved",
            "approved": True,
            "approver_id": decided_by,
            "executed": False,
            "external_execution": False,
            "database_mutation": False,
            "parameters": execution_parameters,
            "data": data,
        }

        queue_job = None
        if approval.execution_id:
            queue_job = AutomationQueueJob.query.filter_by(
                organization_id=int(approval.organization_id),
                execution_id=str(approval.execution_id),
            ).order_by(AutomationQueueJob.id.desc()).first()
        execution_key = str(queue_job.job_key) if queue_job is not None else f"approval:{approval.id}"

        try:
            from app.core.execution.authorization import execution_authorization

            if queue_job is not None:
                plan["job_id"] = int(queue_job.id)
                plan["execution_key"] = execution_key
                plan["idempotency_key"] = str(queue_job.idempotency_key or execution_key)

            authorization = execution_authorization.create_authorization(
                plan,
                approver_id=decided_by,
            )

            plan["plan_id"] = authorization["plan_id"]
            plan["plan_hash"] = authorization["plan_hash"]
            from app.core.execution.approval_gate_adapter import create_runtime_handoff
            handoff = create_runtime_handoff(
                plan, approver_id=decided_by, execution_key=execution_key
            )
            authorization["gate_handoff"] = handoff.as_dict()
            authorization["execution_key"] = execution_key
            from app.core.federation.execution_envelope import execution_envelope
            envelope = execution_envelope.build(
                approval_package_hash=handoff.package_hash,
                decision_hash=handoff.decision_hash,
                handoff_hash=handoff.handoff_hash,
                authorization=authorization,
                execution_key=execution_key,
                provider_id="kemet",
                action=action_type,
            )
            authorization["execution_envelope"] = envelope
            plan["execution_envelope"] = envelope

        except Exception as exc:
            db.session.rollback()
            return {
                "success": False,
                "approval_id": approval_id,
                "status": "pending",
                "message": (
                    "Execution authorization creation failed: "
                    f"{exc}"
                ),
            }

        approval.status = "approved"
        approval.decided_by = decided_by
        approval.decided_at = datetime.utcnow()

        # Persist the authorization BEFORE any execution attempt.
        approval.decision_json = json.dumps(
            {
                "success": True,
                "status": "authorized",
                "plan": plan,
                "authorization": authorization,
            },
            ensure_ascii=False,
            default=str,
        )

        db.session.add(approval)

        if queue_job is not None:
            execution_key = str(authorization.get("execution_key") or queue_job.job_key)
            plan_hash = str(authorization.get("plan_hash") or plan.get("plan_hash") or "")
            from app.core.automation_queue import automation_queue
            automation_queue.bind_execution_envelope(
                queue_job.id, plan=plan, authorization=authorization, commit=False
            )
            workflow_coordinator.transition_approval(
                queue_job.id, WorkflowState.APPROVED,
                approval_id=approval.id, reason="human_approval_granted",
                metadata={"plan_hash": plan_hash, "execution_key": execution_key, "decision_hash": handoff.decision_hash},
                commit=False,
            )
            workflow_coordinator.transition_execution(
                queue_job.id, WorkflowState.QUEUED,
                execution_key=execution_key, reason="approved_for_execution",
                metadata={"approval_id": approval.id, "plan_hash": plan_hash, "decision_hash": handoff.decision_hash},
                commit=False,
            )
            db.session.commit()
            return {
                "success": True,
                "approval_id": approval.id,
                "status": "approved",
                "action": approval.action_type,
                "execution": {"status": "queued", "job_id": queue_job.id},
                "authorization": authorization,
            }

        execution_result = None

        if approval.execution_id:
            try:
                from app.automation.engine import engine

                execution_result = engine.resume_after_approval(
                    approval_id=approval.id,
                    execution_id=approval.execution_id,
                    workflow_id=approval.workflow_id,
                    organization_id=approval.organization_id,
                )

                return {
                    "success": True,
                    "approval_id": approval.id,
                    "status": "approved",
                    "action": approval.action_type,
                    "execution": execution_result,
                    "authorization": authorization,
                }

            except Exception as exc:
                db.session.rollback()

                approval = db.session.get(AutomationApproval, approval_id)

                if approval is not None:
                    approval.status = "approved"
                    approval.decided_by = decided_by
                    approval.decided_at = datetime.utcnow()

                    approval.decision_json = json.dumps(
                        {
                            "success": True,
                            "status": "authorized",
                            "plan": plan,
                            "authorization": authorization,
                            "resume_failed": True,
                            "error": str(exc),
                        },
                        ensure_ascii=False,
                        default=str,
                    )

                    db.session.commit()

                return {
                    "success": False,
                    "approval_id": approval_id,
                    "status": "approved",
                    "message": (
                        "Approval granted, but authorized automation "
                        "resume failed: "
                        f"{exc}"
                    ),
                }

        return {
            "success": True,
            "approval_id": approval.id,
            "status": "approved",
            "action": approval.action_type,
            "execution": execution_result,
            "authorization": authorization,
        }

    def reject(self, approval_id, decided_by=None, reason=None):
        approval = db.session.get(AutomationApproval, approval_id)

        if approval is None:
            return {
                "success": False,
                "message": "Approval request not found.",
            }

        if approval.status != "pending":
            return {
                "success": False,
                "message": "Approval request is not pending.",
                "status": approval.status,
            }

        queue_job = None
        if approval.execution_id:
            queue_job = AutomationQueueJob.query.filter_by(
                organization_id=int(approval.organization_id),
                execution_id=str(approval.execution_id),
            ).order_by(AutomationQueueJob.id.desc()).first()

        try:
            if queue_job is not None and queue_job.workflow_state == WorkflowState.WAITING_APPROVAL:
                workflow_coordinator.transition_approval(
                    queue_job.id, WorkflowState.REJECTED,
                    approval_id=approval.id,
                    reason=reason or "human_approval_rejected",
                    commit=False,
                )

            approval.status = "rejected"
            approval.decided_by = decided_by
            approval.decided_at = datetime.utcnow()

            if reason:
                approval.decision_json = json.dumps(
                    {"reason": reason},
                    ensure_ascii=False,
                )

            if approval.execution_id:
                execution = db.session.get(
                    AutomationExecution, approval.execution_id
                )

                if execution is not None:
                    execution.status = "rejected"
                    execution.error_message = reason or "Human approval rejected."
                    execution.completed_at = datetime.utcnow()
                    db.session.add(execution)

            db.session.add(approval)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return {
            "success": True,
            "approval_id": approval.id,
            "status": "rejected",
            "action": approval.action_type,
        }


automation_approval_service = AutomationApprovalService()
