import json
from datetime import datetime

from app import db
from app.models.automation import (
    AutomationApproval,
    AutomationExecution,
)


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

        try:
            from app.core.execution.authorization import execution_authorization

            authorization = execution_authorization.create_authorization(
                plan,
                approver_id=decided_by,
            )

            plan["plan_id"] = authorization["plan_id"]
            plan["plan_hash"] = authorization["plan_hash"]

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
        db.session.commit()

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

        approval.status = "rejected"
        approval.decided_by = decided_by
        approval.decided_at = datetime.utcnow()

        if reason:
            approval.decision_json = json.dumps(
                {"reason": reason},
                ensure_ascii=False,
            )

        # A rejected approval must not remain waiting forever.
        if approval.execution_id:
            execution = AutomationExecution.query.get(
                approval.execution_id
            )

            if execution is not None:
                execution.status = "rejected"
                execution.error_message = reason or "Human approval rejected."
                execution.completed_at = datetime.utcnow()

                db.session.add(execution)

        db.session.commit()

        return {
            "success": True,
            "approval_id": approval.id,
            "status": "rejected",
            "action": approval.action_type,
        }


automation_approval_service = AutomationApprovalService()
