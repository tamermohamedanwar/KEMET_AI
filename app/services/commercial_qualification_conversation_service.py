from __future__ import annotations

from typing import Any

from app import db
from app.models.demo_lead import DemoLead
from app.models.revenue_pipeline import RevenuePipelineRecord
from app.services.commercial_offer_service import commercial_offer_service
from app.services.channel_adapter_service import channel_adapter_service


class CommercialQualificationConversationService:
    VERSION = "1.0"
    QUESTIONS = {
        "desired_service": "ما الخدمة التي تحتاجها؟",
        "business_need": "ما المشكلة أو الهدف التجاري الذي تريد أن تحققَه بهذه الخدمة؟",
        "scope": "ما نطاق العمل المطلوب؟ اذكر ما تريد أن يشمله العمل والحجم التقريبي إن أمكن.",
        "target_deadline": "متى تريد تنفيذ أو تسليم العمل؟",
        "decision_authority": "هل أنت صاحب قرار الشراء، أم أن شخصًا آخر مسؤول عن اعتماد القرار؟",
    }
    REQUIRED = tuple(QUESTIONS)

    @staticmethod
    def _record(organization_id: int, pipeline_key: str) -> RevenuePipelineRecord:
        return commercial_offer_service._record(organization_id, pipeline_key)

    @staticmethod
    def _conversation(record: RevenuePipelineRecord) -> dict[str, Any]:
        metadata = dict(record.metadata_json or {})
        return dict(metadata.get("commercial_qualification_conversation") or {})

    @staticmethod
    def _save(record: RevenuePipelineRecord, conversation: dict[str, Any]) -> None:
        metadata = dict(record.metadata_json or {})
        metadata["commercial_qualification_conversation"] = conversation
        record.metadata_json = metadata

    @staticmethod
    def _meaningful(text: str) -> bool:
        value = " ".join(str(text or "").strip().split())
        if len(value) < 2:
            return False
        return value.casefold() not in {"ok", "تمام", "نعم", "yes", "no", "لا", "شكرا", "thanks"}

    def start_or_resume(self, *, organization_id: int, pipeline_key: str,
                        channel: str = "telegram") -> dict[str, Any]:
        record = self._record(organization_id, pipeline_key)
        conversation = self._conversation(record)
        qualification = dict((record.metadata_json or {}).get("commercial_qualification") or {})
        answers = dict(conversation.get("answers") or {})
        for field in self.REQUIRED:
            if field in qualification and str(qualification[field] or "").strip():
                answers[field] = qualification[field]
        missing = [field for field in self.REQUIRED if not str(answers.get(field) or "").strip()]
        if not missing:
            return {"success": True, "status": "qualified", "missing_fields": [],
                    "governance": self._governance()}
        next_field = missing[0]
        conversation.update({"status": "qualification_in_progress", "answers": answers,
                              "next_field": next_field, "missing_fields": missing})
        self._save(record, conversation)
        db.session.commit()
        return self._plan(record, next_field, missing, channel)

    def ingest_answer(self, *, organization_id: int, pipeline_key: str, text: str,
                      external_message_id: str, channel: str = "telegram") -> dict[str, Any]:
        record = self._record(organization_id, pipeline_key)
        conversation = self._conversation(record)
        external_message_id = str(external_message_id or "").strip()
        if not external_message_id:
            raise ValueError("external_message_id_required")
        existing_evidence = dict(conversation.get("evidence") or {})
        if any(str(item.get("external_message_id") or "").strip() == external_message_id for item in existing_evidence.values() if isinstance(item, dict)):
            return {
                "success": True,
                "status": "duplicate_external_message",
                "next_field": conversation.get("next_field"),
                "missing_fields": list(conversation.get("missing_fields") or []),
                "governance": self._governance(),
            }
        next_field = str(conversation.get("next_field") or "").strip()
        if not next_field or next_field not in self.REQUIRED:
            return self.start_or_resume(organization_id=organization_id, pipeline_key=pipeline_key, channel=channel)
        if not self._meaningful(text):
            return self._plan(record, next_field, list(conversation.get("missing_fields") or []), channel,
                              status="answer_not_specific_enough")
        answers = dict(conversation.get("answers") or {})
        answers[next_field] = str(text).strip()[:1000]
        evidence = dict(conversation.get("evidence") or {})
        evidence[next_field] = {"source": f"{str(channel).strip().lower()}.customer", "external_message_id": str(external_message_id),
                                "channel": str(channel).strip().lower()}
        conversation["answers"] = answers
        conversation["evidence"] = evidence
        missing = [field for field in self.REQUIRED if not str(answers.get(field) or "").strip()]
        if missing:
            conversation.update({"status": "qualification_in_progress", "next_field": missing[0],
                                 "missing_fields": missing})
            self._save(record, conversation)
            db.session.commit()
            return self._plan(record, missing[0], missing, channel)
        qualification = dict(answers)
        qualification["evidence"] = evidence
        result = commercial_offer_service.qualify(
            organization_id=organization_id, pipeline_key=pipeline_key,
            qualification=qualification,
        )
        conversation.update({"status": "qualified", "next_field": None, "missing_fields": [],
                              "answers": answers, "evidence": evidence})
        self._save(record, conversation)
        db.session.commit()
        return {"success": True, "status": "qualified", "qualification": result,
                "governance": self._governance()}

    def _plan(self, record: RevenuePipelineRecord, field: str, missing: list[str],
              channel: str, status: str = "qualification_in_progress") -> dict[str, Any]:
        content = self.QUESTIONS[field]
        response = channel_adapter_service.response_plan(
            channel=channel, organization_id=int(record.organization_id),
            content=content, requires_approval=True,
        )
        return {"success": True, "status": status, "pipeline_id": record.id,
                "lead_id": record.lead_id, "next_field": field,
                "missing_fields": missing, "question": content,
                "response_plan": response, "governance": self._governance()}

    @staticmethod
    def _governance() -> dict[str, bool]:
        return {"external_execution": False, "auto_execute": False, "human_approval_required": True}


commercial_qualification_conversation_service = CommercialQualificationConversationService()
