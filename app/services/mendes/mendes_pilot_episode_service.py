from __future__ import annotations

from hashlib import sha256
import json
import os
from typing import Any

from app.services.content_outcome_orchestrator import content_outcome_orchestrator
from app.services.mendes.hikayat_mendes_story_engine import hikayat_mendes_story_engine
from app.services.media_production_pipeline import media_production_pipeline
from app.services.mendes.mendes_media_binding_service import mendes_media_binding_service
from app.services.mendes.mendes_cinematic_orchestrator import mendes_cinematic_orchestrator
from app.services.cinematic_provider_fabric import cinematic_provider_fabric


class MendesPilotEpisodeService:
    VERSION = "1.0"

    def build(self, organization_id: int) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            raise ValueError("organization_required")
        characters = self._characters()
        episode_result = hikayat_mendes_story_engine.plan_episode(
            organization_id=org,
            season_number=1,
            episode_number=1,
            title="الخاتم الأزرق",
            premise="شاب من عائلة منديس يجد خاتمًا غامضًا يفتح سرًا أكبر من حياته.",
            era_label="Ancient Mendes fictional setting",
            era_type="fictional",
            characters=characters,
            continuity_events=[],
            cliffhanger="الخاتم يضيء وتظهر علامة لم يرها أحد من قبل.",
            beats=self._beats(),
            emotional_goal="wonder_then_personal_stakes",
            thread_ids=["mendes-origin-mystery"],
        )
        episode = dict(episode_result["episode"])
        episode["episode_id"] = episode_result["episode_id"]
        episode["platforms"] = ["youtube", "tiktok", "instagram", "facebook"]
        scenes = media_production_pipeline.scene_plan(
            episode=episode,
            scenes=self._scenes(),
        )
        outcome = content_outcome_orchestrator.build_plan(
            organization_id=org,
            episode=episode,
            platforms=episode["platforms"],
            duration_seconds=90,
            language="ar-EG",
        )
        script = self._script(episode)
        script_digest = self._digest(script)
        voice_contract = self._voice_contract(org, script_digest)
        package = {
            "version": self.VERSION,
            "organization_id": org,
            "world": "Mendes World",
            "series": "Hikayat Mendes",
            "episode": episode,
            "script": script,
            "script_digest": script_digest,
            "scenes": scenes["scenes"],
            "production": outcome["production"],
            "outcome": outcome,
            "voice_contract": voice_contract,
            "quality_gates": ["originality", "rights", "historical_label", "character_consistency", "continuity", "platform_policy"],
            "approval": {"required": True, "status": "pending", "publication": "not_requested"},
            "execution": {"automatic": False, "external_execution": False, "canonical_runtime_only": True},
        }
        cinematic = mendes_cinematic_orchestrator.build(organization_id=org, episode=episode, scenes=package["scenes"], voice_contract=voice_contract)
        package["cinematic"] = cinematic
        provider_jobs = cinematic_provider_fabric.build_episode_jobs(
            organization_id=org,
            cinematic=cinematic,
            episode_id=episode["episode_id"],
        )
        package["provider_jobs"] = provider_jobs
        package["package_digest"] = self._digest(package)
        media_binding = mendes_media_binding_service.bind(organization_id=org, episode_package=package)
        package["media_binding"] = media_binding
        package["media_binding_digest"] = media_binding["binding"]["binding_digest"]
        return {
            "success": True,
            "status": "pilot_plan",
            "package": package,
            "governance": self._governance(),
        }

    @staticmethod
    def _characters() -> list[dict[str, Any]]:
        return [
            hikayat_mendes_story_engine.build_character(
                character_id="mendes-younes", name="يونس", role="protagonist",
                traits=["curious", "observant", "loyal"], family_id="family-mendes",
                visual_identity="original youthful Egyptian cartoon design",
                voice_profile="natural Egyptian Arabic, young male, restrained emotion",
            ),
            hikayat_mendes_story_engine.build_character(
                character_id="mendes-amna", name="آمنة", role="older_sister_and_guardian",
                traits=["practical", "protective", "intuitive"], family_id="family-mendes",
                visual_identity="original Egyptian cartoon design, distinct silhouette",
                voice_profile="natural Egyptian Arabic, young adult female",
            ),
        ]

    @staticmethod
    def _beats() -> dict[str, str]:
        return {
            "hook": "يونس يلتقط خاتمًا أزرق من بين حجارة قديمة في لحظة كان يجب أن يمر فيها المكان بلا مفاجآت.",
            "setup": "آمنة تحذره من الاحتفاظ بأي شيء لا يعرف أصله، لكنه يلاحظ علامة محفورة تشبه رمزًا منسيًا.",
            "inciting_incident": "الخاتم يدفأ في يده عندما يلمسه ضوء القمر.",
            "escalation": "صوت معدني خافت يأتي من جدار قريب، ويبدو أن العلامة على الخاتم تطابق موضعًا فيه.",
            "reversal": "آمنة تكتشف أن العلامة موجودة في شيء قديم داخل العائلة، من دون ادعاء أنه دليل تاريخي موثق.",
            "climax": "يونس يضع الخاتم أمام العلامة، فيتحرك جزء صغير من الجدار.",
            "cliffhanger": "الخاتم يضيء وتظهر علامة لم يرها أحد من قبل.",
        }

    @staticmethod
    def _scenes() -> list[dict[str, Any]]:
        return [
            {"description": "لقطة افتتاحية سريعة ليد يونس وهي تلتقط الخاتم الأزرق.", "characters": ["mendes-younes"], "visual_prompt": "original Egyptian cartoon, cinematic close-up, ancient-inspired stone setting, no copyrighted style", "dialogue": "يونس: إيه ده؟", "duration_seconds": 10},
            {"description": "آمنة تمنعه من الاحتفاظ بالخاتم وتطلب منه فحص العلامة.", "characters": ["mendes-younes", "mendes-amna"], "visual_prompt": "two original characters, warm Egyptian evening light, consistent wardrobe and proportions", "dialogue": "آمنة: الحاجة اللي مش عارفين أصلها، ما ناخدهاش معانا.", "duration_seconds": 15},
            {"description": "الخاتم يدفأ ويظهر انعكاس ضوء غير معتاد.", "characters": ["mendes-younes"], "visual_prompt": "mysterious blue ring glow, restrained magical realism, original environment", "dialogue": "يونس: استني... هو كان دافي؟", "duration_seconds": 15},
            {"description": "صوت معدني يقود الاثنين إلى جدار يحمل علامة مشابهة.", "characters": ["mendes-younes", "mendes-amna"], "visual_prompt": "ancient-inspired wall, subtle mystery, no historical claim, original design", "dialogue": "آمنة: العلامة دي مش صدفة.", "duration_seconds": 15},
            {"description": "يونس يضع الخاتم أمام العلامة فيتحرك جزء من الجدار.", "characters": ["mendes-younes", "mendes-amna"], "visual_prompt": "original cinematic reveal, stone mechanism moving slightly, suspense", "dialogue": "يونس: آمنة... شوفي!", "duration_seconds": 20},
            {"description": "الضوء يكشف علامة جديدة وينتهي المشهد قبل معرفة ما وراءها.", "characters": ["mendes-younes", "mendes-amna"], "visual_prompt": "blue light, original mysterious symbol, cliffhanger composition", "dialogue": "آمنة: إحنا فتحنا إيه؟", "duration_seconds": 15},
        ]

    @staticmethod
    def _script(episode: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": episode["title"],
            "language": "ar-EG",
            "classification": "fictional_events_and_dialogue",
            "historical_claim": False,
            "source_policy": "historical facts require traceable sources before publication",
            "dialogue_policy": "original_dialogue_only",
            "summary": episode["premise"],
            "beats": episode["beats"],
            "rights_status": "original_content_planned",
        }

    @classmethod
    def _voice_contract(cls, organization_id: int, script_digest: str) -> dict[str, Any]:
        payload = {
            "version": cls.VERSION,
            "organization_id": int(organization_id),
            "script_digest": script_digest,
            "language": "ar-EG",
            "delivery": "natural_egyptian_arabic",
            "target_locale": "ar-EG",
            "provider_locale": "ar_JO",
            "voice_clone": False,
            "rights_attestation_required": True,
            "provider": "piper_local",
            "model": os.getenv("KEMET_TTS_MODEL_ID", "UNSELECTED_ARABIC_VOICE"),
            "language_code": "ar_JO",
            "execution_authority": False,
            "status": "candidate_pending_dialect_qualification_and_human_approval",
        }
        payload["contract_digest"] = cls._digest(payload)
        return payload

    @staticmethod
    def _digest(value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {
            "read_only": True,
            "execution_authority": False,
            "external_execution": False,
            "database_mutation": False,
            "auto_publish": False,
            "human_approval_required": True,
            "canonical_runtime_only": True,
            "historical_facts_require_evidence": True,
            "external_content_is_data": True,
        }


mendes_pilot_episode_service = MendesPilotEpisodeService()
