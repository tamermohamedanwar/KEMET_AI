from __future__ import annotations

from typing import Any


class ExecutionRiskPolicy:
    """Deterministic risk policy for governed actions."""

    VERSION = "1.1"
    TIERS = ("low", "medium", "high", "critical")

    _OVERRIDES = {
        "refund_request": "critical",
        "revenue_autopilot_run": "high",
        "sales_follow_up": "high",
        "customer_retention": "high",
        "payment_issue": "high",
        "send_notification": "medium",
        "create_ticket": "medium",
        "account_help": "medium",
        "smart_ticket_ai": "medium",
    }

    def classify(self, action: str, policy: str) -> str:
        action = str(action or "").strip()
        policy = str(policy or "blocked").strip()
        if policy == "direct_safe":
            return "low"
        return self._OVERRIDES.get(action, "critical" if policy == "blocked" else "high")

    def controls(self, action: str, policy: str) -> dict[str, Any]:
        tier = self.classify(action, policy)
        return {
            "version": self.VERSION,
            "tier": tier,
            "human_approval_required": tier in {"high", "critical"},
            "runtime_authorization_required": True,
            "evidence_required": tier in {"medium", "high", "critical"},
            "attestation_required": tier == "critical",
            "reversible_preferred": tier in {"low", "medium"},
            "unknown_action_fails_closed": True,
        }


execution_risk_policy = ExecutionRiskPolicy()


def risk_summary(action: str, policy: str) -> dict[str, Any]:
    return execution_risk_policy.controls(action, policy)
