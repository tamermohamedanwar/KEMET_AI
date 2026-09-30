import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services.commercial_qualification_conversation_service import (
    CommercialQualificationConversationService,
)


class CommercialQualificationConversationTests(unittest.TestCase):
    def setUp(self):
        self.service = CommercialQualificationConversationService()
        self.record = SimpleNamespace(
            id=1,
            lead_id=7,
            organization_id=1,
            pipeline_key="test-pipeline",
            metadata_json={"telegram": {"chat_id": "test-chat"}},
        )
        self.commit = patch("app.services.commercial_qualification_conversation_service.db.session.commit")
        self.commit.start()
        self.record_patch = patch.object(
            CommercialQualificationConversationService,
            "_record",
            return_value=self.record,
        )
        self.record_patch.start()

    def tearDown(self):
        self.record_patch.stop()
        self.commit.stop()

    def test_start_is_approval_gated_and_does_not_mutate_external_channel(self):
        result = self.service.start_or_resume(
            organization_id=1, pipeline_key="test-pipeline", channel="telegram"
        )
        self.assertEqual(result["status"], "qualification_in_progress")
        self.assertEqual(result["next_field"], "desired_service")
        self.assertTrue(result["response_plan"]["requires_approval"])
        self.assertFalse(result["response_plan"]["governance"]["external_execution"])

    def test_non_specific_answer_does_not_advance(self):
        self.service.start_or_resume(
            organization_id=1, pipeline_key="test-pipeline", channel="telegram"
        )
        result = self.service.ingest_answer(
            organization_id=1, pipeline_key="test-pipeline",
            text="تمام", external_message_id="m1", channel="telegram"
        )
        self.assertEqual(result["status"], "answer_not_specific_enough")
        self.assertEqual(result["next_field"], "desired_service")

    def test_all_five_explicit_answers_qualify_with_evidence(self):
        self.service.start_or_resume(
            organization_id=1, pipeline_key="test-pipeline", channel="telegram"
        )
        qualified = {
            "status": "qualified",
            "complete": True,
            "required_fields": list(self.service.REQUIRED),
            "provided_fields": list(self.service.REQUIRED),
        }
        with patch(
            "app.services.commercial_qualification_conversation_service.commercial_offer_service.qualify",
            return_value=qualified,
        ) as qualify:
            answers = [
                ("desired_service", "فيديو إعلاني تجاري"),
                ("business_need", "زيادة العملاء المحتملين"),
                ("scope", "فيديو 45 ثانية مع نسخة للسوشيال"),
                ("target_deadline", "خلال أسبوعين"),
                ("decision_authority", "أنا صاحب القرار"),
            ]
            result = None
            for index, (_, answer) in enumerate(answers, start=1):
                result = self.service.ingest_answer(
                    organization_id=1, pipeline_key="test-pipeline",
                    text=answer, external_message_id=f"m{index}", channel="telegram"
                )
            self.assertEqual(result["status"], "qualified")
            qualify.assert_called_once()
            payload = qualify.call_args.kwargs["qualification"]
            self.assertEqual(payload["desired_service"], "فيديو إعلاني تجاري")
            self.assertEqual(payload["decision_authority"], "أنا صاحب القرار")
            self.assertEqual(payload["evidence"]["desired_service"]["external_message_id"], "m1")
            self.assertEqual(payload["evidence"]["decision_authority"]["external_message_id"], "m5")

    def test_duplicate_external_message_is_idempotent(self):
        self.service.start_or_resume(
            organization_id=1, pipeline_key="test-pipeline", channel="telegram"
        )
        first = self.service.ingest_answer(
            organization_id=1, pipeline_key="test-pipeline",
            text="خدمة فيديو إعلاني", external_message_id="same-message", channel="telegram"
        )
        self.assertEqual(first["status"], "qualification_in_progress")
        duplicate = self.service.ingest_answer(
            organization_id=1, pipeline_key="test-pipeline",
            text="خدمة مختلفة", external_message_id="same-message", channel="telegram"
        )
        self.assertEqual(duplicate["status"], "duplicate_external_message")
        self.assertEqual(duplicate["next_field"], "business_need")


    def test_replay_after_qualification_does_not_create_another_offer(self):
        self.record.metadata_json["commercial_qualification_conversation"] = {
            "status": "qualified",
            "answers": {field: "explicit" for field in self.service.REQUIRED},
            "next_field": None,
            "missing_fields": [],
        }
        result = self.service.ingest_answer(
            organization_id=1, pipeline_key="test-pipeline",
            text="new unrelated message", external_message_id="m-replay", channel="telegram"
        )
        self.assertEqual(result["status"], "qualified")
        self.assertNotIn("offer", result)


if __name__ == "__main__":
    unittest.main()
