from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.automation.playbook_engine import playbook_engine


class CapabilityRegistry:
    """Read-only production registry composed from governed playbooks."""

    VERSION = "1.0"
    LIFECYCLE = {"draft", "active", "deprecated", "disabled"}

    LIFECYCLE_DEFAULT = "active"

    def __init__(self) -> None:
        self._overrides = {
            "refund_request": {"lifecycle": "active", "tags": ["finance", "approval"]},
            "business_insights": {"lifecycle": "active", "tags": ["insights", "read_only"]},
        }

    def _definition(self, action: str) -> dict[str, Any] | None:
        definition = playbook_engine.get_definition(action)
        if not definition:
            return None
        meta = self._overrides.get(action, {})
        item = deepcopy(definition)
        item.update(meta)
        item.setdefault("lifecycle", self.LIFECYCLE_DEFAULT)
        item.setdefault("tags", [item.get("domain", "general")])
        item["capability_id"] = f"kemet.{action}"
        item["registry_version"] = self.VERSION
        item["expected_outcomes"] = [item.get("outcome", "")] if item.get("outcome") else []
        item["metrics"] = [
            {"key": "execution_success_rate", "unit": "percent", "source": "automation"},
            {"key": "business_outcome_status", "unit": "status", "source": "outcome"},
        ]
        item["governance"] = {
            "advisory": True,
            "fail_closed": True,
            "requires_approval": action == "refund_request",
            "external_execution": False,
            "database_mutation": False,
        }
        item["execution_profile"] = {
            "mode": "governed_sequential",
            "checkpointing": True,
            "resumable": True,
            "retry_policy": {"max_attempts": 2, "backoff_seconds": 1},
        }
        return item

    def catalog(self, lifecycle: str | None = None) -> list[dict[str, Any]]:
        if lifecycle is not None and lifecycle not in self.LIFECYCLE:
            raise ValueError("Invalid capability lifecycle.")
        items = [self._definition(action) for action in playbook_engine.PLAYBOOK_CATALOG]
        return [item for item in items if item and (lifecycle is None or item["lifecycle"] == lifecycle)]

    def get(self, capability_id: str) -> dict[str, Any] | None:
        if not capability_id.startswith("kemet."):
            return None
        return self._definition(capability_id.removeprefix("kemet."))

    def plan(self, capability_id: str, parameters: dict[str, Any] | None = None) -> dict[str, Any]:
        definition = self.get(capability_id)
        if not definition or definition["lifecycle"] != "active":
            raise ValueError("Capability is unavailable.")
        action = definition["action"]
        plan = {"action": action, "intent": definition["name"], "parameters": parameters or {}, "confidence": 1.0}
        playbook = playbook_engine.build(plan)
        return {"success": True, "status": "planned", "capability": definition, "playbook": playbook}


capability_registry = CapabilityRegistry()
