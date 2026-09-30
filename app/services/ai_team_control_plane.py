from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from app.core.task_planner import task_planner
from app.workforce.registry import workforce_registry


class AITeamControlPlane:
    VERSION = "1.0"

    GOVERNANCE = {
        "execution_authority": False,
        "external_execution": False,
        "auto_execute": False,
        "human_approval_required": True,
        "canonical_runtime_only": True,
        "mcp": False,
    }

    @staticmethod
    def _digest(value: Any) -> str:
        return sha256(
            json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()
        ).hexdigest()

    def team_snapshot(self, organization_id: int) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        members = []
        for profile in workforce_registry.list():
            members.append({
                "id": profile["id"],
                "name": profile["name"],
                "role": profile["role"],
                "description": profile["description"],
                "industries": profile["industries"],
                "status": profile["status"],
            })
        payload = {"version": self.VERSION, "organization_id": int(organization_id), "members": members}
        return {**payload, "member_count": len(members), "team_digest": self._digest(payload), "governance": dict(self.GOVERNANCE)}

    def assignment_preview(
        self,
        organization_id: int,
        workforce_id: str,
        objective: str,
        *,
        issue_id: str | None = None,
        action: str | None = None,
    ) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            raise ValueError("organization_required")
        objective = str(objective or "").strip()
        if not objective:
            raise ValueError("objective_required")
        employee = workforce_registry.get(workforce_id)
        if employee is None:
            return {"status": "BLOCKED", "error": "workforce_not_found", "governance": dict(self.GOVERNANCE)}
        classification = task_planner.classify(objective)
        plan = task_planner.plan(objective, organization_id=org, task_id=str(issue_id or "assignment"))
        selected_action = str(action or "").strip() or (plan.steps[0].action if plan.steps else "")
        validation = workforce_registry.can_execute(workforce_id, selected_action)
        requires_approval = selected_action in employee.get("approval_actions", []) or plan.requires_approval
        payload = {
            "version": self.VERSION,
            "organization_id": org,
            "workforce_id": workforce_id,
            "role": employee.get("role"),
            "objective": objective,
            "issue_id": issue_id,
            "action": selected_action,
            "action_allowed": bool(validation),
            "classification": {
                "task_type": classification.task_type,
                "risk": classification.risk,
                "confidence": classification.confidence,
                "capabilities": sorted(classification.capabilities),
            },
            "plan_hash": plan.plan_hash,
            "requires_approval": bool(requires_approval),
            "assignment_state": "READY_FOR_APPROVAL" if requires_approval else "READY",
        }
        return {
            **payload,
            "assignment_digest": self._digest(payload),
            "governance": dict(self.GOVERNANCE),
        }

    def mention_preview(self, organization_id: int, mention: str, objective: str) -> dict[str, Any]:
        token = str(mention or "").strip().lstrip("@").lower()
        if not token:
            raise ValueError("mention_required")
        return self.assignment_preview(organization_id, token, objective)

    def schedule_preview(self, organization_id: int, workforce_id: str, objective: str, schedule: str) -> dict[str, Any]:
        assignment = self.assignment_preview(organization_id, workforce_id, objective)
        payload = {
            "organization_id": int(organization_id),
            "workforce_id": workforce_id,
            "objective": objective,
            "schedule": str(schedule or "").strip(),
            "assignment_digest": assignment.get("assignment_digest"),
        }
        if not payload["schedule"]:
            raise ValueError("schedule_required")
        return {
            "status": "SCHEDULE_PROPOSAL",
            "schedule": payload["schedule"],
            "assignment": assignment,
            "schedule_digest": self._digest(payload),
            "governance": dict(self.GOVERNANCE),
        }


ai_team_control_plane = AITeamControlPlane()
