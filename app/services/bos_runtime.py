from __future__ import annotations

import json
from datetime import datetime

from app import db
from app.automation.engine import engine
from app.automation.orchestrator import orchestrator
from app.automation.playbook_engine import playbook_engine
from app.models.automation import AutomationAction, AutomationExecution, AutomationWorkflow


class BOSRuntime:
    """Real governed business-operation runtime."""

    def plan(self, command: str):
        plan = orchestrator.plan(command)
        return playbook_engine.build(plan)

    def operate(self, command: str, organization_id: int, user_id: int | None = None):
        plan = orchestrator.plan(command)
        playbook = playbook_engine.build(plan)
        workflow = self._materialize(plan, playbook, organization_id)
        if plan.get("requires_approval"):
            return self._prepare_approval(
                command, plan, playbook, workflow, organization_id, user_id
            )
        results = engine.execute(
            event="manual_command",
            data={"command": command, "organization_id": organization_id, "user_id": user_id},
            organization_id=organization_id,
            workflow_id=workflow.id,
        )
        waiting = next((item for item in results if item.get("status") == "waiting_approval"), None)
        return {
            "success": not bool(waiting),
            "status": "waiting_approval" if waiting else "completed",
            "plan": plan,
            "playbook": playbook,
            "workflow_id": workflow.id,
            "approval_id": waiting.get("approval_id") if waiting else None,
            "approval_required": bool(waiting),
            "executed": not bool(waiting),
            "results": results,
        }

    def _prepare_approval(self, command, plan, playbook, workflow, organization_id, user_id):
        from app.services.automation_approval_service import automation_approval_service
        action = playbook["steps"][0]
        idempotency_key = engine._build_idempotency_key(
            workflow_id=workflow.id,
            event="manual_command",
            data={"command": command, "organization_id": organization_id, "user_id": user_id},
            organization_id=organization_id,
        )
        execution = AutomationExecution(
            workflow_id=workflow.id,
            trigger_type="manual_command",
            idempotency_key=idempotency_key,
            status="waiting_approval",
            input_json=json.dumps(
                {"command": command, "plan": plan, "playbook": playbook},
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
            action_type=action["action"],
            reason=plan.get("approval_reason") or "Human approval required before this action.",
            request_data={"action_id": workflow.actions[0].id, "action": action["action"], "parameters": action.get("parameters") or {}, "data": {"command": command, "organization_id": organization_id, "user_id": user_id}},
            workflow_id=workflow.id,
            execution_id=execution.id,
            requested_by=user_id,
        )
        return {"success": False, "status": "waiting_approval", "plan": plan, "playbook": playbook, "workflow_id": workflow.id, "approval_id": approval.get("approval_id"), "approval_required": True, "executed": False}

    def approve(self, approval_id: int, organization_id: int, user_id: int):
        from app.services.automation_approval_service import automation_approval_service
        if not self._approval_belongs_to_org(approval_id, organization_id):
            return {"success": False, "status": "blocked", "error": "approval_not_in_organization"}
        return automation_approval_service.approve(approval_id, decided_by=user_id)

    def reject(self, approval_id: int, organization_id: int, user_id: int, reason: str | None = None):
        from app.services.automation_approval_service import automation_approval_service
        if not self._approval_belongs_to_org(approval_id, organization_id):
            return {"success": False, "status": "blocked", "error": "approval_not_in_organization"}
        return automation_approval_service.reject(approval_id, decided_by=user_id, reason=reason)

    def _approval_belongs_to_org(self, approval_id: int, organization_id: int) -> bool:
        from app.models.automation import AutomationApproval
        return AutomationApproval.query.filter_by(id=approval_id, organization_id=organization_id).first() is not None

    def _materialize(self, plan, playbook, organization_id):
        name = f"Kemet Command · {plan['action']} · {datetime.utcnow():%Y%m%d%H%M%S}"
        workflow = AutomationWorkflow(
            organization_id=organization_id,
            name=name,
            description="Command-center generated governed business workflow.",
            trigger_type="manual_command",
            is_active=True,
        )
        db.session.add(workflow)
        db.session.flush()
        for step in playbook["steps"]:
            db.session.add(AutomationAction(
                workflow_id=workflow.id,
                position=step["position"],
                action_type=step["action"],
                config_json=json.dumps(step.get("parameters") or {}, ensure_ascii=False),
                is_active=True,
            ))
        db.session.commit()
        return workflow


bos_runtime = BOSRuntime()
