from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


VOICE_CHANNEL = "voice"
SUPPORTED_CALL_STATES = frozenset({"ringing", "in_progress", "completed", "failed"})
INTENTS = frozenset({
    "sales_inquiry",
    "appointment_request",
    "support_request",
    "order_inquiry",
    "billing_inquiry",
    "unknown",
})


@dataclass(frozen=True)
class VoiceCallEvent:
    organization_id: int
    external_call_id: str
    caller_id: str
    state: str
    text: str = ""
    language: str = "en"
    intent: str = "unknown"
    metadata: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "external_call_id": self.external_call_id,
            "caller_id": self.caller_id,
            "channel": VOICE_CHANNEL,
            "state": self.state,
            "text": self.text,
            "language": self.language,
            "intent": self.intent,
            "metadata": dict(self.metadata or {}),
        }


class VoiceCallService:
    VERSION = "1.0"

    def normalize(
        self,
        *,
        organization_id: int,
        external_call_id: str,
        caller_id: str,
        state: str,
        text: str = "",
        language: str | None = None,
        intent: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> VoiceCallEvent:
        if organization_id <= 0:
            raise ValueError("organization_required")
        if not external_call_id or not caller_id:
            raise ValueError("call_identity_required")
        normalized_state = str(state or "").strip().lower()
        if normalized_state not in SUPPORTED_CALL_STATES:
            raise ValueError("unsupported_call_state")
        normalized_text = str(text or "").strip()
        detected_language = language or self._detect_language(normalized_text)
        normalized_intent = str(intent or "unknown").strip().lower()
        if normalized_intent not in INTENTS:
            normalized_intent = "unknown"
        return VoiceCallEvent(
            organization_id=organization_id,
            external_call_id=str(external_call_id).strip(),
            caller_id=str(caller_id).strip(),
            state=normalized_state,
            text=normalized_text,
            language=detected_language,
            intent=normalized_intent,
            metadata=metadata or {},
        )

    def commercial_context(
        self,
        event: VoiceCallEvent,
        *,
        execution_key: str | None = None,
    ) -> dict[str, Any]:
        """Build an evidence-ready commercial context without mutating state."""
        completed = event.state == "completed"
        normalized_execution_key = str(execution_key or "").strip()
        return {
            "channel": VOICE_CHANNEL,
            "interaction_id": event.external_call_id,
            "organization_id": event.organization_id,
            "intent": event.intent,
            "commercial_stage": "interaction_completed" if completed else "interaction_active",
            "outcome_status": "candidate" if completed else "not_ready",
            "execution_link": {
                "status": "provided" if normalized_execution_key else "not_provided",
                "execution_key": normalized_execution_key or None,
            },
            "revenue": {
                "status": "not_available",
                "source": None,
                "causal_claim": False,
            },
            "roi": {
                "status": "not_proven",
                "causal_claim": False,
            },
            "governance": {
                "read_only": True,
                "database_mutation": False,
                "external_execution": False,
            },
        }

    def route(self, event: VoiceCallEvent) -> dict[str, Any]:
        return {
            "channel": VOICE_CHANNEL,
            "call_id": event.external_call_id,
            "organization_id": event.organization_id,
            "intent": event.intent,
            "language": event.language,
            "next": "kemet_core",
            "governance": {
                "read_only": True,
                "advisory": True,
                "external_execution": False,
                "database_mutation": False,
                "auto_execute": False,
                "human_approval_required": True,
            },
            "commercial_outcome_ready": event.state == "completed",
        }

    @staticmethod
    def _detect_language(text: str) -> str:
        arabic = sum("\u0600" <= char <= "\u06ff" for char in text)
        latin = sum("a" <= char.lower() <= "z" for char in text)
        return "ar" if arabic > latin else "en"


voice_call_service = VoiceCallService()
