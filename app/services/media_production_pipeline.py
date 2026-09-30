from __future__ import annotations

from typing import Any, Mapping

from app.services.production_studio_service import production_studio_service
from app.services.autoclip_capability_service import autoclip_capability_service
from app.services.native_shortform_service import native_shortform_service
from app.services.native_transcription_service import native_transcription_service
from app.services.media_approval_packet_service import media_approval_packet_service


class MediaProductionPipeline:
    VERSION = "1.1"
    OUTPUTS = ("script", "scenes", "images", "animation", "voice", "music", "sound_effects", "edit")
    LANGUAGES = ("ar-EG", "ar", "en")

    def build_plan(self, *, organization_id: int, episode: Mapping[str, Any], language: str = "ar-EG",
                   duration_seconds: int = 90, source_video_uri: str | None = None,
                   transcript: list[Mapping[str, Any]] | None = None,
                   content_intent: str | None = None) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        if not isinstance(episode, Mapping) or not episode.get("title"):
            raise ValueError("episode_required")
        language = str(language or "").strip()
        if language not in self.LANGUAGES:
            raise ValueError("unsupported_language")
        if duration_seconds < 30 or duration_seconds > 600:
            raise ValueError("duration_out_of_range")
        title = str(episode["title"]).strip()[:200]
        studio_plan = production_studio_service.plan(
            organization_id=int(organization_id), title=title, language=language,
            duration_seconds=int(duration_seconds),
            platforms=list(episode.get("platforms") or ["youtube", "tiktok", "instagram"]),
            reference_uri=episode.get("reference_uri"),
        )
        shortform = None
        native_shortform = None
        if source_video_uri:
            shortform = autoclip_capability_service.plan(
                organization_id=int(organization_id), input_uri=str(source_video_uri),
                language=language, clip_count=5, aspect_ratio="9:16",
            )
            native_shortform = native_shortform_service.plan(
                organization_id=int(organization_id), input_uri=str(source_video_uri),
                language=language, clip_count=5, aspect_ratio="9:16", transcript=transcript,
            )
        intent = str(content_intent or episode.get("content_intent") or "video").strip().lower()
        stage_map = {
            "image": ["brief", "asset_generation", "asset_qa", "provenance"],
            "audio": ["brief", "voice_or_sound_generation", "audio_qa", "mastering", "provenance"],
            "voice": ["script", "voice_generation", "voice_qa", "mastering", "provenance"],
            "document": ["brief", "research_or_source_binding", "draft", "text_qa", "provenance"],
            "social_post": ["brief", "copy", "creative_asset", "platform_qa", "provenance"],
            "video": ["script", "scenes", "images", "animation", "voice", "music", "sound_effects", "edit", "qa", "provenance"],
            "commercial": ["script", "scenes", "assets", "voice", "music", "edit", "qa", "provenance"],
            "educational": ["research", "script", "scenes", "visual_assets", "voice", "subtitles", "qa", "provenance"],
            "cartoon": ["story", "characters", "worlds", "scenes", "animation", "voice", "sound", "qa", "provenance"],
            "animation": ["story", "characters", "worlds", "scenes", "animation", "voice", "sound", "qa", "provenance"],
            "motion_graphics": ["script", "design_assets", "motion", "voice", "sound", "qa", "provenance"],
            "short": ["hook", "script", "assets", "voice", "edit", "qa", "provenance"],
            "long_form": ["research", "story", "script", "sequences", "assets", "voice", "sound", "edit", "qa", "provenance"],
        }
        stages = [{"stage": stage, "status": "planned"} for stage in stage_map.get(intent, stage_map["video"])]
        if source_video_uri:
            stages.append({"stage": "shortform", "status": "planned", "capability": "kemet_native_shortform", "reference_capability": "autoclip_local_shortform"})
        else:
            stages.append({"stage": "shortform", "status": "optional", "capability": "kemet_native_shortform", "reference_capability": "autoclip_local_shortform"})
        return {
            "success": True, "pipeline": "kemet_media_production", "version": self.VERSION,
            "status": "production_plan", "organization_id": int(organization_id),
            "episode_title": title, "language": language,
            "source_video": {"provided": bool(source_video_uri), "uri": source_video_uri if source_video_uri else None},
            "shortform": shortform, "native_shortform": native_shortform,
            "duration_seconds": int(duration_seconds), "production_studio": studio_plan,
            "stages": stages,
            "quality_gates": {
                "originality": "required", "rights": "required", "historical_label": "required",
                "character_consistency": "required", "continuity": "required", "platform_policy": "required",
            },
            "external_generation": {"allowed": True, "execution_authority": False, "provider_is_untrusted": True},
            "governance": {"mode": "advisory", "human_approval_required": True,
                           "canonical_executor": "kemet_canonical_runtime"},
        }

    def build_transcribed_shortform_plan(self, *, organization_id: int, input_uri: str,
                                         language: str = "ar", clip_count: int = 5,
                                         aspect_ratio: str = "9:16") -> dict[str, Any]:
        transcription = native_transcription_service.transcribe(
            organization_id=int(organization_id), input_uri=str(input_uri), language=str(language or "ar"),
        )
        if not transcription.get("success"):
            return {
                "success": False,
                "status": "transcription_blocked",
                "transcription": transcription,
                "governance": self._governance(),
            }
        plan = native_shortform_service.plan(
            organization_id=int(organization_id), input_uri=str(input_uri),
            language=str(language or "ar"), clip_count=int(clip_count),
            aspect_ratio=str(aspect_ratio or "9:16"), transcript=transcription.get("transcript") or [],
        )
        if not plan.get("success"):
            return {
                "success": False,
                "status": "shortform_blocked",
                "transcription": {
                    "status": transcription.get("status"),
                    "transcript_digest": transcription.get("transcript_digest"),
                    "segment_count": len(transcription.get("transcript") or []),
                },
                "shortform": plan,
                "governance": self._governance(),
            }
        plan_payload = plan.get("plan") if isinstance(plan.get("plan"), Mapping) else plan
        task_id = f"media-shortform-{str(plan_payload.get('plan_digest'))[:16]}"
        approval_packet = media_approval_packet_service.build(
            organization_id=int(organization_id),
            task_id=task_id,
            transcription=transcription,
            shortform=plan,
        )
        return {
            "success": True,
            "status": "transcribed_shortform_approval_ready",
            "task_id": task_id,
            "transcription": {
                "status": transcription.get("status"),
                "transcript_digest": transcription.get("transcript_digest"),
                "segment_count": len(transcription.get("transcript") or []),
            },
            "shortform": plan,
            "approval_packet": approval_packet,
            "governance": self._governance(),
        }

    def scene_plan(self, *, episode: Mapping[str, Any], scenes: list[Mapping[str, Any]]) -> dict[str, Any]:
        if not isinstance(episode, Mapping) or not episode.get("title"):
            raise ValueError("episode_required")
        if not scenes:
            raise ValueError("scenes_required")
        normalized = []
        for index, scene in enumerate(scenes, start=1):
            if not isinstance(scene, Mapping) or not str(scene.get("description") or "").strip():
                raise ValueError("scene_description_required")
            normalized.append({"scene_number": index, "description": str(scene["description"]).strip()[:1000],
                               "characters": [str(x)[:120] for x in (scene.get("characters") or [])],
                               "visual_prompt": str(scene.get("visual_prompt") or "").strip()[:2000],
                               "dialogue": str(scene.get("dialogue") or "").strip()[:3000],
                               "duration_seconds": int(scene.get("duration_seconds") or 0)})
        return {"success": True, "status": "scene_plan", "scenes": normalized,
                "execution_authority": False, "governance": self._governance()}

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {"mode": "advisory", "read_only": True, "execution_authority": False,
                "external_execution": False, "human_approval_required": True,
                "canonical_executor": "kemet_canonical_runtime"}


media_production_pipeline = MediaProductionPipeline()
