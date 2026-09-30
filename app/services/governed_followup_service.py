import hashlib
import json
from typing import Any, Mapping


class GovernedFollowupService:
    VERSION = "1.0"
    ALLOWED_CHANNELS = {"voice", "web", "whatsapp", "telegram", "email"}

    def build_plan(self, *, organization_id: int, qualification: Mapping[str, Any],
                   channel: str = "voice", customer_id: Any = None,
                   lead_id: Any = None, message_goal: str = "sales_follow_up") -> dict[str, Any]:
        if not organization_id:
            raise ValueError("organization_id_required")
        channel = str(channel or "voice").strip().lower()
        if channel not in self.ALLOWED_CHANNELS:
            raise ValueError("unsupported_followup_channel")
        status = str(qualification.get("status") or "").strip().lower()
        if status != "qualified":
            return self._blocked(organization_id, channel, status)
        if list(qualification.get("missing_fields") or []):
            return self._blocked(organization_id, channel, status, "qualification_incomplete")
        payload = {"organization_id": int(organization_id), "lead_id": lead_id,
                   "customer_id": customer_id, "channel": channel,
                   "message_goal": str(message_goal or "sales_follow_up"), "action": "sales_follow_up"}
        proposal_key = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        return {"success": True, "status": "approval_required", "type": "governed_follow_up_plan",
                "version": self.VERSION, "organization_id": int(organization_id),
                "customer_id": customer_id, "lead_id": lead_id, "channel": channel,
                "message_goal": str(message_goal or "sales_follow_up"), "action": "sales_follow_up",
                "proposal_key": proposal_key,
                "approval": {"required": True, "reason": "Customer-facing follow-up is a consequential external action."},
                "execution": {"canonical_action": "sales_follow_up", "executor": "kemet_canonical_runtime",
                               "external_execution": False, "auto_execute": False},
                "commercial": {"revenue": "not_available", "roi": "not_proven", "causal_claim": False},
                "governance": self._governance()}

    @staticmethod
    def _governance():
        return {"read_only": True, "advisory": True, "database_mutation": False,
                "external_execution": False, "auto_execute": False, "human_approval_required": True}

    @staticmethod
    def _blocked(organization_id, channel, status, reason="qualification_not_ready"):
        return {"success": True, "status": "blocked", "type": "governed_follow_up_plan",
                "version": GovernedFollowupService.VERSION, "organization_id": int(organization_id),
                "channel": channel, "action": "sales_follow_up", "reason": reason,
                "qualification_status": status, "approval": {"required": True},
                "execution": {"external_execution": False, "auto_execute": False},
                "commercial": {"revenue": "not_available", "roi": "not_proven", "causal_claim": False},
                "governance": GovernedFollowupService._governance()}


governed_followup_service = GovernedFollowupService()

