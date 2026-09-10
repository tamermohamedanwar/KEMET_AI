import json
from datetime import datetime

from app import db
from app.models.automation import (
    AutomationAction,
    AutomationApproval,
    AutomationExecution,
    AutomationWorkflow,
)
from app.services.automation_approval_service import (
    automation_approval_service,
)


class BOSApprovalService:
    """
    Bridges a BOS business decision into the canonical automation
    approval and cryptographic execution path.

    This service never executes an action while preparing approval.
    Execution occurs only through AutomationApprovalService.approve(),
    which creates authorization and resumes through the execution gate.
    """

    def prepare(
        self,
        organization_id,
        action_type,
        reason,
        data=None,
        requested_by=None,
    ):
        if not organization_id:
            return {
                "success": False,
                "status": "blocked",
                "error": "organization_required",
            }

        if not action_type:
            return {
                "success": False,
                "status": "blocked",
                "error": "action_required",
            }

        data = dict(data or {})
        data["organization_id"] = organization_id

        workflows = (
            AutomationWorkflow.query
            .filter_by(
                organization_id=organization_id,
                is_active=True,
            )
            .order_by(AutomationWorkflow.id.asc())
            .all()
        )

        matches = []

        for workflow in workflows:
            actions = (
                AutomationAction.query
                .filter_by(
                    workflow_id=workflow.id,
                    is_active=True,
                )
                .order_by(AutomationAction.position.asc())
                .all()
            )

            if len(actions) != 1:
                continue

            action = actions[0]

            if action.action_type != action_type:
                continue

            matches.append((workflow, action))

        if not matches:
            return {
                "success": False,
                "status": "blocked",
                "error": "direct_workflow_not_found",
                "action": action_type,
                "organization_id": organization_id,
            }

        workflow, action = matches[0]

        config = {}

        if action.config_json:
            try:
                parsed = json.loads(action.config_json)
                if isinstance(parsed, dict):
                    config = parsed
            except Exception:
                config = {}

        execution = AutomationExecution(
            workflow_id=workflow.id,
            trigger_type="bos_decision",
            status="waiting_approval",
            input_json=json.dumps(
                data,
                ensure_ascii=False,
                default=str,
            ),
            started_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )

        db.session.add(execution)
        db.session.flush()

        approval = automation_approval_service.create(
            organization_id=organization_id,
            action_type=action.action_type,
            reason=reason,
            request_data={
                "action_id": action.id,
                "action": action.action_type,
                "parameters": config,
                "data": data,
            },
            workflow_id=workflow.id,
            execution_id=execution.id,
            requested_by=requested_by,
        )

        if not approval.get("success"):
            db.session.rollback()
            return {
                **approval,
                "status": "blocked",
            }

        execution.output_json = json.dumps(
            [{
                "action_id": action.id,
                "action_type": action.action_type,
                "status": "waiting_approval",
                "approval_id": approval.get("approval_id"),
            }],
            ensure_ascii=False,
            default=str,
        )

        execution.completed_at = None
        db.session.add(execution)
        db.session.commit()

        return {
            "success": True,
            "status": "waiting_approval",
            "organization_id": organization_id,
            "workflow_id": workflow.id,
            "workflow_name": workflow.name,
            "action_id": action.id,
            "action": action.action_type,
            "execution_id": execution.id,
            "approval_id": approval.get("approval_id"),
            "approval_required": True,
            "requires_human": True,
        }

    def approve(
        self,
        approval_id,
        decided_by=None,
    ):
        return automation_approval_service.approve(
            approval_id=approval_id,
            decided_by=decided_by,
        )

    def reject(
        self,
        approval_id,
        decided_by=None,
        reason=None,
    ):
        return automation_approval_service.reject(
            approval_id=approval_id,
            decided_by=decided_by,
            reason=reason,
        )


bos_approval_service = BOSApprovalService()
