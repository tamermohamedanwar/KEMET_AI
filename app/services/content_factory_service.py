"""Governed Content Factory for Kemet.

Builds a complete content proposal without executing external side effects.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.services.content_outcome_orchestrator import content_outcome_orchestrator
from app.services.mendes.hikayat_mendes_story_engine import hikayat_mendes_story_engine
from app.services.media_production_pipeline import media_production_pipeline
from app.services.social_distribution_hub import social_distribution_hub
from app.services.content_experiment_service import content_experiment_service
from app.services.telegram_audience_service import telegram_audience_service
from app.services.mirofish_simulation_service import mirofish_simulation_service
from app.services.visual_direction_service import visual_direction_service
from app.services.capability_registry import capability_registry
from app.services.generation_router import generation_router
from app.core.media.contracts import CONTENT_INTENT, build_contract


class ContentFactoryService:
    VERSION = "1.1"
    SCHEMA = "kemet.content_factory.v1"
    PLATFORMS = ("youtube", "facebook", "instagram", "tiktok", "linkedin")
    CONTENT_INTENTS = {
        "video": "cinematic", "image": "photoreal", "audio": "audio", "voice": "voice",
        "document": "document", "social_post": "social_post", "short": "social_short",
        "long_form": "long_form", "commercial": "commercial", "advertisement": "commercial",
        "educational": "educational", "documentary": "documentary", "story": "story_narrative",
        "cartoon": "cartoon", "animation": "animation", "motion_graphics": "motion_graphics",
        "explainer": "explainer", "product_content": "product_film", "business_content": "corporate_film",
        "series": "story_narrative", "episode": "story_narrative", "repurposed_content": "social_short",
        "commentary": "social_short", "product": "product_film",
    }
    CONTENT_TYPES = tuple(CONTENT_INTENTS)
    RIGHTS = ("original", "licensed", "public_domain", "user_supplied", "pending_review")

    def build(self, *, organization_id: int, title: str, premise: str,
              audience: str = "Arabic-speaking audience", content_type: str = "story",
              language: str = "ar-EG", dialect: str = "eg", production_profile: str = "story",
              platforms: list[str] | None = None,
              duration_seconds: int = 90, source_ids: list[str] | None = None,
              source_video_uri: str | None = None,
              rights_status: str = "original", era_label: str | None = None,
              era_type: str = "inspired", season_number: int | None = None,
              episode_number: int | None = None, characters: list[Mapping[str, Any]] | None = None,
              beats: Mapping[str, str] | None = None, emotional_goal: str = "",
              cliffhanger: str = "") -> dict[str, Any]:
        self._org(organization_id)
        self._text(title, "title_required", 200)
        self._text(premise, "premise_required", 3000)
        self._text(audience, "audience_required", 500)
        intent = str(content_type or "").strip().lower()
        if intent not in self.CONTENT_INTENTS:
            raise ValueError("unsupported_content_intent")
        if language not in {"ar-EG", "ar", "en"}:
            raise ValueError("unsupported_language")
        allowed_dialects = {"eg", "msa", "sa", "sd", "levant", "maghreb", "en"}
        if dialect not in allowed_dialects:
            raise ValueError("unsupported_dialect")
        profile_id = str(production_profile or "").strip().lower()
        if profile_id == "story":
            profile_id = "story_narrative"
        if profile_id == "auto":
            profile_id = self._profile_for_intent(intent)
        if not str(production_profile or "").strip() or str(production_profile).strip().lower() == "default":
            profile_id = self._profile_for_intent(intent)
        if not profile_id:
            raise ValueError("production_profile_required")
        profile = visual_direction_service.production_profile(profile_id)
        if rights_status not in self.RIGHTS:
            raise ValueError("unsupported_rights_status")
        selected = self._platforms(platforms)
        if rights_status == "pending_review":
            rights_gate = "BLOCKED_PENDING_RIGHTS"
        else:
            rights_gate = "PASS"

        story = {
            "title": title.strip()[:200], "premise": premise.strip()[:3000],
            "audience": audience.strip()[:500], "content_type": intent, "content_intent": intent,
            "language": language, "dialect": dialect, "production_profile": profile_id,
            "production_profile_digest": profile["digest"],
            "platforms": list(selected),
            "source_ids": [str(x)[:160] for x in (source_ids or [])],
            "rights_status": rights_status,
            "claims": self._claims_contract(),
            "version": 1,
            "lifecycle_state": "DRAFT",
        }
        if era_label:
            if era_type not in hikayat_mendes_story_engine.ERA_TYPES:
                raise ValueError("invalid_era_type")
            story["era"] = {"label": str(era_label)[:120], "type": era_type}
        if season_number and episode_number:
            story_plan = hikayat_mendes_story_engine.plan_episode(
                organization_id=organization_id, season_number=season_number,
                episode_number=episode_number, title=title, premise=premise,
                era_label=era_label or "Unspecified", era_type=era_type,
                characters=characters, beats=beats, emotional_goal=emotional_goal,
                cliffhanger=cliffhanger,
            )
            story.update(story_plan["episode"])
            story["episode_id"] = story_plan["episode_id"]
        media = media_production_pipeline.build_plan(
            organization_id=organization_id, episode=story,
            language=language, duration_seconds=duration_seconds,
            source_video_uri=source_video_uri, content_intent=intent,
        )
        quality = self.quality_gate(
            title=title, premise=premise, rights_status=rights_status,
            source_ids=source_ids or [], story=story, media=media,
        )
        shortform = media.get("shortform")
        if source_video_uri and not shortform:
            raise ValueError("shortform_plan_required")
        distribution = social_distribution_hub.plan(
            organization_id, asset_uri="pending:approved_media_asset",
            title=title, caption=premise, platforms=list(selected),
        )
        outcome = content_outcome_orchestrator.build_plan(
            organization_id=organization_id, episode=story,
            platforms=list(selected), duration_seconds=duration_seconds,
            language=language,
        )
        experiment = content_experiment_service.build(
            organization_id=organization_id,
            content_id=outcome["content_id"],
            title=title,
            audience=audience,
            hook=str((beats or {}).get("hook") or title),
            story=premise,
            cta="Continue the story on Telegram.",
            platforms=list(selected) + ["telegram"],
        )
        telegram = telegram_audience_service.build_funnel(
            organization_id=organization_id,
            channel_ref="pending:telegram_channel",
            content_id=outcome["content_id"],
        )
        simulation = mirofish_simulation_service.build_simulation_request(
            organization_id=organization_id,
            content_id=outcome["content_id"],
            seed_digest=experiment["experiment_digest"],
            question="Compare audience reaction to the opening hook, story framing and Telegram continuation CTA.",
        )
        approval = self._approval_package(story, quality, distribution, media)
        capabilities = capability_registry.media_catalog(organization_id)
        capability_requirements = self._capability_requirements(intent=intent, profile_id=profile_id, duration_seconds=duration_seconds, source_video_uri=source_video_uri)
        production_spec_payload = {
            "organization_id": int(organization_id), "content_intent": intent,
            "business_objective": emotional_goal or "create_and_distribute_content",
            "audience": audience.strip()[:500], "language": language, "dialect": dialect,
            "platforms": list(selected), "duration_seconds": int(duration_seconds),
            "production_profile": profile_id, "story": dict(story),
            "references": {"source_ids": list(source_ids or []), "source_video_uri": source_video_uri},
            "requirements": capability_requirements, "governance": self._governance(),
        }
        production_spec = build_contract(CONTENT_INTENT, organization_id=int(organization_id), payload=production_spec_payload, contract_id=f"content-{self._digest(production_spec_payload)[:24]}")
        production_spec["contract_type"] = CONTENT_INTENT
        production_spec["digest"] = self._digest({k:v for k,v in production_spec.items() if k != "digest"})
        routing_decision = generation_router.route(
            organization_id=int(organization_id),
            content_intent=intent,
            production_spec=production_spec,
            capability_requirements=capability_requirements,
        )
        capability_resolution = dict(routing_decision.get("capability_resolution") or {})
        resolved_requirements = list(capability_resolution.get("requirements") or [])
        from app.services.cinematic_production_os import cinematic_production_os
        production_state = cinematic_production_os.build_state(
            organization_id=int(organization_id),
            project_id=f"content-{production_spec['contract_id']}",
            stage="production_specification",
            canonical_refs={"production_spec_digest": production_spec["digest"]},
            visual_direction={"id": profile_id, "digest": profile["digest"]},
            intent={"content_intent": intent, "task_type": intent},
        )
        memory_payload = {
            "schema": "kemet.cinematic.production_memory.v1",
            "version": 1,
            "organization_id": int(organization_id),
            "project_id": production_state["project_id"],
            "characters": [dict(x) for x in (characters or [])],
            "worlds": [dict(x) for x in ([dict(story.get("era"))] if story.get("era") else [])],
            "style": {"profile_id": profile_id, "profile_digest": profile["digest"]},
            "voices": [],
            "continuity_state": [],
            "canonical": True,
            "policy": {"unapproved_outputs_are_noncanonical": True},
        }
        memory_payload["digest"] = self._digest(memory_payload)
        canonical_graph = cinematic_production_os.build_canonical_graph(
            state=production_state, production_spec=production_spec,
            capability_requirements=resolved_requirements, routing_decision=routing_decision,
            memory=memory_payload, characters=characters or [], worlds=[dict(story.get("era"))] if story.get("era") else [],
            project={"project_id": production_state["project_id"], "digest": production_state["digest"]},
            episode={"id": story.get("episode_id"), "digest": story.get("digest")} if story.get("episode_id") else None,
        )
        production_plan = {
            "schema": "kemet.production_plan.v1",
            "understood": {"title": title, "premise": premise, "audience": audience, "objective": emotional_goal or "create_and_distribute_content"},
            "content_intent": intent, "production_profile": profile, "production_spec": production_spec,
            "duration_seconds": int(duration_seconds), "language": language, "dialect": dialect,
            "expected_shots": max(1, min(24, round(int(duration_seconds) / 6))) if intent not in {"image", "audio", "voice", "document", "social_post"} else 0,
            "characters": list(characters or []), "worlds": [dict(story.get("era"))] if story.get("era") else [],
            "capability_requirements": capability_requirements, "resolved_capability_requirements": resolved_requirements, "capabilities": capabilities,
            "routing_decision": routing_decision, "production_state": production_state,
            "production_graph": canonical_graph, "production_memory": memory_payload,
            "quality_inputs": {"content_intent": intent, "production_graph_digest": canonical_graph["digest"], "memory_digest": memory_payload["digest"], "language": language, "dialect": dialect},
            "quality_gates": quality["checks"], "approval_required": True,
            "external_execution": False, "canonical_runtime_only": True,
        }
        production_plan["digest"] = self._digest(production_plan)
        package = {
            "schema": self.SCHEMA, "version": self.VERSION,
            "organization_id": int(organization_id), "status": "review_required",
            "content": story, "idea": self._idea_contract(story),
            "production": media, "production_plan": production_plan, "shortform": shortform,
            "quality_gate": quality,
            "approval": approval, "distribution": distribution,
            "measurement": outcome["measurement"], "learning": outcome["learning"],
            "content_experiment": experiment,
            "telegram_audience": telegram,
            "simulation": simulation,
            "governance": self._governance(),
        }
        package["package_digest"] = self._digest(package)
        return package

    @staticmethod
    def _profile_for_intent(intent: str) -> str:
        # Reuse the existing visual-direction profile system; non-visual outputs
        # intentionally bind to the existing custom profile rather than creating
        # a second profile architecture.
        return {
            "video": "cinematic",
            "image": "photoreal",
            "audio": "custom",
            "voice": "custom",
            "document": "custom",
            "social_post": "social_post",
            "short": "social_short",
            "long_form": "long_form",
            "commercial": "commercial",
            "advertisement": "commercial",
            "educational": "educational",
            "documentary": "documentary",
            "story": "story_narrative",
            "cartoon": "cartoon",
            "animation": "animation",
            "motion_graphics": "motion_graphics",
            "explainer": "explainer",
            "product_content": "product_film",
            "business_content": "corporate_film",
            "series": "story_narrative",
            "episode": "story_narrative",
            "repurposed_content": "social_short",
            "commentary": "social_short",
            "product": "product_film",
        }.get(intent, "custom")

    @staticmethod
    def _capability_requirements(*, intent: str, profile_id: str, duration_seconds: int, source_video_uri: str | None) -> list[dict[str, Any]]:
        base = {
            "video": ["TEXT_GENERATION", "VIDEO_GENERATION", "COMPOSITING", "RENDERING"],
            "image": ["TEXT_GENERATION", "IMAGE_GENERATION"],
            "audio": ["TEXT_GENERATION", "SOUND_GENERATION", "MUSIC_GENERATION", "COMPOSITING"],
            "voice": ["TEXT_GENERATION", "TEXT_TO_SPEECH", "VOICE_SYNTHESIS", "COMPOSITING"],
            "document": ["TEXT_GENERATION"],
            "social_post": ["TEXT_GENERATION"],
        }
        video_intents = {"commercial", "advertisement", "educational", "documentary", "story", "cartoon", "animation", "motion_graphics", "explainer", "product_content", "business_content", "series", "episode", "short", "long_form", "repurposed_content", "commentary"}
        if intent in video_intents:
            required = ["TEXT_GENERATION", "VIDEO_GENERATION", "COMPOSITING", "RENDERING"]
            required += ["TEXT_TO_SPEECH", "VOICE_SYNTHESIS", "SOUND_GENERATION"]
        else:
            required = list(base.get(intent, ["TEXT_GENERATION"]))
        if source_video_uri or intent == "repurposed_content":
            required = list(dict.fromkeys(required + ["VIDEO_UNDERSTANDING", "TRANSCRIPTION", "SUBTITLE_GENERATION"]))
        return [{"capability": cap, "required": True, "reason": "derived_from_content_intent_and_production_profile"} for cap in required]

    def quality_gate(self, *, title: str, premise: str, rights_status: str,
                     source_ids: list[str], story: Mapping[str, Any],
                     media: Mapping[str, Any]) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        checks.append(self._check("creative_value", bool(title.strip() and premise.strip()),
                                  "title_and_premise_present"))
        checks.append(self._check("originality", rights_status in {"original", "licensed", "public_domain", "user_supplied"},
                                  "source_rights_status_declared"))
        checks.append(self._check("provenance", bool(source_ids) or rights_status == "original",
                                  "source_trace_or_original_declaration"))
        checks.append(self._check("historical_label", bool(story.get("historical_label_required", False)) is False or
                                  bool((story.get("era") or {}).get("label")),
                                  "historical_material_is_labeled"))
        checks.append(self._check("production_quality", bool(media.get("quality_gates")),
                                  "production_quality_gates_present"))
        checks.append(self._check("platform_policy", True, "policy_check_required_at_publish_preflight"))
        checks.append(self._check("rights", rights_status != "pending_review", "rights_are_not_pending"))
        blocked = [item["name"] for item in checks if not item["passed"]]
        return {
            "schema": "kemet.content_quality_gate.v1", "status": "BLOCKED" if blocked else "PASS",
            "checks": checks, "blocked_by": blocked,
            "promotion": "approval_allowed" if not blocked else "approval_blocked",
            "human_review_required": True, "external_execution": False,
        }

    def _idea_contract(self, story: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "topic": story.get("title"), "premise": story.get("premise"),
            "audience": story.get("audience"), "format": story.get("content_type"),
            "platforms": story.get("platforms", []),
            "signals": {"demand_score": None, "competition_score": None,
                        "monetization_score": None, "confidence": "unmeasured"},
            "rule": "never invent demand_or_monetization_measurements",
        }

    @staticmethod
    def _claims_contract() -> dict[str, Any]:
        return {
            "schema": "kemet.content_claims.v1",
            "categories": [
                "observed_fact",
                "provided_business_input",
                "derived_metric",
                "forecast",
                "recommendation",
                "unsupported_needs_review",
            ],
            "forecast_is_not_recorded_revenue": True,
            "unsupported_claims_require_human_review": True,
            "fabricated_social_proof_forbidden": True,
        }

    @staticmethod
    def _approval_package(story: Mapping[str, Any], quality: Mapping[str, Any],
                          distribution: Mapping[str, Any], media: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "required": True, "decision": "PENDING",
            "scope": "content_package",
            "checks": {
                "creative": quality["status"] == "PASS",
                "rights": quality["checks"][1]["passed"],
                "production": bool(media.get("production_studio")),
                "distribution": bool(distribution.get("targets")),
            },
            "side_effects": {"publish": False, "external_generation": False},
            "review_summary": {
                "title": story.get("title"), "content_type": story.get("content_type"),
                "rights_status": story.get("rights_status"),
            },
        }

    @staticmethod
    def _check(name: str, passed: bool, evidence: str) -> dict[str, Any]:
        return {"name": name, "passed": bool(passed), "evidence": evidence}

    @classmethod
    def _platforms(cls, platforms: Any) -> tuple[str, ...]:
        values = cls.PLATFORMS if platforms is None else platforms
        if isinstance(values, str):
            values = [values]
        result = tuple(dict.fromkeys(str(x).strip().lower() for x in values if str(x).strip()))
        if not result or any(x not in cls.PLATFORMS for x in result):
            raise ValueError("unsupported_platform")
        return result

    @staticmethod
    def _text(value: Any, error: str, limit: int) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError(error)
        return text[:limit]

    @staticmethod
    def _org(value: Any) -> None:
        if int(value or 0) <= 0:
            raise ValueError("organization_required")

    @staticmethod
    def _digest(payload: Mapping[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {"mode": "advisory", "read_only": True, "execution_authority": False,
                "external_execution": False, "auto_publish": False,
                "human_approval_required": True, "canonical_executor": "kemet_canonical_runtime"}


content_factory_service = ContentFactoryService()
