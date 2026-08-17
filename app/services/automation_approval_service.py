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
        approval = AutomationApproval.query.get(approval_id)

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

        approval.status = "approved"
        approval.decided_by = decided_by
        approval.decided_at = datetime.utcnow()

        db.session.flush()

        # ---------------------------------------------------------
        # Resume the paused automation execution.
        # ---------------------------------------------------------
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

                if isinstance(execution_result, dict):
                    approval.decision_json = json.dumps(
                        execution_result,
                        ensure_ascii=False,
                        default=str,
                    )

            except Exception as exc:
                db.session.rollback()

                approval = AutomationApproval.query.get(approval_id)

                if approval is not None:
                    approval.status = "approved"
                    approval.decided_by = decided_by
                    approval.decided_at = datetime.utcnow()
                    approval.decision_json = json.dumps(
                        {
                            "success": False,
                            "error": str(exc),
                            "resume_failed": True,
                        },
                        ensure_ascii=False,
                        default=str,
                    )

                    db.session.commit()

                return {
                    "success": False,
                    "approval_id": approval_id,
                    "status": "approved",
                    "message": f"Approval granted, but automation resume failed: {exc}",
                }

        db.session.commit()

        return {
            "success": True,
            "approval_id": approval.id,
            "status": "approved",
            "action": approval.action_type,
            "execution": execution_result,
        }

    def reject(self, approval_id, decided_by=None, reason=None):
        approval = AutomationApproval.query.get(approval_id)

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
