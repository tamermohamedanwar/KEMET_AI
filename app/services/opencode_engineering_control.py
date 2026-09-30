from __future__ import annotations

import json
from hashlib import sha256
from typing import Any


class OpenCodeEngineeringControl:
    VERSION = "1.0"
    SCHEMA = "kemet.opencode_engineering_control.v1"

    GOVERNANCE = {
        "role_model": "primary_subagent",
        "permission_model": "allow_ask_deny",
        "execution_authority": False,
        "external_execution": False,
        "auto_execute": False,
        "human_approval_required": True,
        "canonical_runtime_only": True,
        "mcp": False,
        "sandbox_required_for_untrusted": True,
        "advisory_external_dev_bridge": True,
    }

    PROFILES = {
        "plan": {
            "mode": "primary",
            "purpose": "analysis_and_plan",
            "permissions": {"read": "allow", "edit": "deny", "bash": "ask", "task": "deny"},
        },
        "build": {
            "mode": "primary",
            "purpose": "implementation",
            "permissions": {"read": "allow", "edit": "ask", "bash": "ask", "task": "ask"},
        },
        "review": {
            "mode": "subagent",
            "purpose": "read_only_review",
            "permissions": {"read": "allow", "edit": "deny", "bash": "deny", "task": "deny"},
        },
        "test_runner": {
            "mode": "subagent",
            "purpose": "verification",
            "permissions": {"read": "allow", "edit": "deny", "bash": "ask", "task": "deny"},
        },
        "explore": {
            "mode": "subagent",
            "purpose": "codebase_exploration",
            "permissions": {"read": "allow", "edit": "deny", "bash": "ask", "task": "deny"},
        },
    }

    @staticmethod
    def _digest(value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
        return sha256(raw.encode("utf-8")).hexdigest()

    def role_catalog(self) -> dict[str, Any]:
        payload = {"schema": self.SCHEMA, "version": self.VERSION, "roles": self.PROFILES, "governance": self.GOVERNANCE}
        return {**payload, "catalog_digest": self._digest(payload)}

    def plan(self, objective: str, organization_id: int) -> dict[str, Any]:
        org = int(organization_id or 0)
        text = str(objective or "").strip()
        if org <= 0:
            raise ValueError("organization_required")
        if not text:
            raise ValueError("objective_required")
        steps = [
            {"stage": "PLAN", "role": "plan", "purpose": "understand_scope_and_constraints"},
            {"stage": "BUILD", "role": "build", "purpose": "prepare_proposed_change"},
            {"stage": "REVIEW", "role": "review", "purpose": "independent_read_only_review"},
            {"stage": "VERIFY", "role": "test_runner", "purpose": "run_governed_verification"},
        ]
        payload = {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "organization_id": org,
            "objective": text,
            "workflow": steps,
            "approval_points": ["before_external_side_effect", "before_canonical_execution"],
            "governance": self.GOVERNANCE,
        }
        return {**payload, "plan_digest": self._digest(payload)}

    def assignment_preview(self, objective: str, organization_id: int, role: str) -> dict[str, Any]:
        catalog = self.role_catalog()
        selected = catalog["roles"].get(str(role or "").strip().lower())
        if selected is None:
            return {"status": "BLOCKED", "error": "engineering_role_not_found", "governance": self.GOVERNANCE}
        payload = {
            "schema": self.SCHEMA,
            "organization_id": int(organization_id),
            "role": str(role).strip().lower(),
            "objective": str(objective or "").strip(),
            "permissions": selected["permissions"],
            "authority": "advisory_only",
        }
        return {"status": "READY_FOR_REVIEW", **payload, "assignment_digest": self._digest(payload), "governance": self.GOVERNANCE}


opencode_engineering_control = OpenCodeEngineeringControl()
