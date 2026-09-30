from dataclasses import dataclass
from typing import Any, Mapping

from app.services.voice_call_service import VoiceCallEvent


QUALIFICATION_FIELDS = (
    "need",
    "budget",
    "timeline",
    "authority",
    "fit",
)


@dataclass(frozen=True)
class QualificationSignal:
    field: str
    value: Any
    confidence: float
    source: str


class VoiceQualificationService:
    VERSION = "1.0"

    def qualify(
        self,
        event: VoiceCallEvent,
        *,
        signals: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if event.state != "completed":
            return self._not_ready(event)

        metadata = dict(event.metadata or {})
        supplied = dict(signals or {})
        metadata_signals = metadata.get("qualification")
        if isinstance(metadata_signals, Mapping):
            supplied = {**dict(metadata_signals), **supplied}

        normalized = {}
        signal_details = []
        for field in QUALIFICATION_FIELDS:
            value = supplied.get(field)
            if value is None or value == "":
                continue
            confidence = self._confidence(value)
            normalized[field] = value
            signal_details.append(
                QualificationSignal(
                    field=field,
                    value=value,
                    confidence=confidence,
                    source="voice_event_metadata",
                ).__dict__
            )

        score = round((len(normalized) / len(QUALIFICATION_FIELDS)) * 100)
        if event.intent == "sales_inquiry":
            score = min(100, score + 10)
        elif event.intent in {"appointment_request", "order_inquiry"}:
            score = min(100, score + 5)

        readiness = "qualified" if score >= 70 else "needs_information"
        if event.intent not in {"sales_inquiry", "appointment_request", "order_inquiry"}:
            readiness = "not_sales_ready"

        next_step = (
            "prepare_follow_up_plan" if readiness == "qualified"
            else "collect_missing_qualification"
        )
        return {
            "success": True,
            "ready": True,
            "channel": "voice",
            "call_id": event.external_call_id,
            "organization_id": event.organization_id,
            "intent": event.intent,
            "qualification": {
                "status": readiness,
                "score": score,
                "signals": normalized,
                "signal_details": signal_details,
                "missing_fields": [f for f in QUALIFICATION_FIELDS if f not in normalized],
            },
            "next_step": next_step,
            "governance": self._governance(),
            "commercial": {
                "outcome_candidate": True,
                "revenue": "not_available",
                "roi": "not_proven",
                "causal_claim": False,
            },
        }

    @staticmethod
    def _confidence(value: Any) -> float:
        if isinstance(value, bool):
            return 0.95
        if isinstance(value, (int, float)):
            return 0.90
        return 0.80 if str(value).strip() else 0.0

    @staticmethod
    def _governance() -> dict[str, bool]:
        return {
            "read_only": True,
            "advisory": True,
            "database_mutation": False,
            "external_execution": False,
            "auto_execute": False,
            "human_approval_required": True,
        }

    def _not_ready(self, event: VoiceCallEvent) -> dict[str, Any]:
        return {
            "success": True,
            "ready": False,
            "channel": "voice",
            "call_id": event.external_call_id,
            "organization_id": event.organization_id,
            "intent": event.intent,
            "qualification": {
                "status": "not_ready",
                "score": 0,
                "signals": {},
                "signal_details": [],
                "missing_fields": list(QUALIFICATION_FIELDS),
            },
            "next_step": "wait_for_completed_call",
            "governance": self._governance(),
            "commercial": {
                "outcome_candidate": False,
                "revenue": "not_available",
                "roi": "not_proven",
                "causal_claim": False,
            },
        }


voice_qualification_service = VoiceQualificationService()
