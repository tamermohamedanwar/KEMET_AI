from __future__ import annotations

from typing import Any


HIGH_RISK_ACTIONS = {
    "refund_request",
    "send_notification",
    "sales_follow_up",
}
APPROVAL_ACTIONS = {"refund_request"}


def build_steps(action: str, parameters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    parameters = dict(parameters or {})
    steps = [{
        "step_id": "step_1",
        "position": 1,
        "action": action,
        "parameters": parameters,
        "risk": "high" if action in HIGH_RISK_ACTIONS else "low",
        "requires_approval": action in APPROVAL_ACTIONS,
        "on_success": "continue",
        "on_failure": "stop",
    }]
    return steps


def summarize_steps(steps: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "step_count": len(steps),
        "approval_steps": sum(1 for step in steps if step.get("requires_approval")),
        "high_risk_steps": sum(1 for step in steps if step.get("risk") == "high"),
        "execution_mode": "governed_sequential",
    }
