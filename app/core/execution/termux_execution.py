from __future__ import annotations

import os
from typing import Any

import requests


class TermuxExecutionError(RuntimeError):
    pass


class TermuxExecutionService:
    VERSION = "1.1"
    ALLOWED_OPERATIONS = frozenset({"health", "test_health", "compile", "git_status"})

    OPERATION_ACTIONS = {
        "health": "termux_engineering",
        "test_health": "termux_engineering",
        "compile": "termux_engineering",
        "git_status": "termux_engineering",
    }

    def __init__(self):
        self.bridge_url = os.getenv("KEMET_BRIDGE_URL", "http://127.0.0.1:8770").rstrip("/")
        self.token = os.getenv("KEMET_AGENT_TOKEN", "").strip()

    def execute(self, *, operation: str, plan: dict[str, Any], authorization: dict[str, Any], action: str) -> dict[str, Any]:
        operation = str(operation or "").strip()
        if operation not in self.ALLOWED_OPERATIONS:
            raise TermuxExecutionError("termux_operation_not_allowed")
        expected_action = self.OPERATION_ACTIONS[operation]
        if action != expected_action:
            raise TermuxExecutionError("termux_action_binding_invalid")
        if not self.token:
            raise TermuxExecutionError("termux_bridge_token_missing")
        response = requests.post(
            f"{self.bridge_url}/termux/run",
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
            json={"operation": operation, "plan": plan, "authorization": authorization, "action": action},
            timeout=130,
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise TermuxExecutionError("termux_invalid_response") from exc
        if response.status_code >= 400 or not payload.get("ok"):
            error = payload.get("error") or "termux_execution_failed"
            raise TermuxExecutionError(str(error))
        return payload


termux_execution = TermuxExecutionService()
