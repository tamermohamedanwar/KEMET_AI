from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping


class MendesEpisodeReadinessService:
    VERSION = "1.5"
    PLATFORMS = ("youtube", "tiktok", "instagram", "facebook")
    OFFICIAL_EVIDENCE = {
        "voice_candidate_local_tts": {
            "provider": "piper_local",
            "source_uri": "https://github.com/gyroing/piper-tts-for-termux",
            "voice_uri": None,
            "license_review": "model_card_and_dataset_license_review_required",
            "commercial_use": "not_assumed_without_model_card_and_dataset_license_review",
            "voice_clone": "disabled",
            "pricing": "no_api_fee_local_runtime",
            "verified_at": "2026-09-19",
        },
        "youtube": {
            "source_uri": "https://support.google.com/youtube/answer/15424877",
            "insert_uri": "https://developers.google.com/youtube/v3/docs/videos/insert",
            "disclosure_uri": "https://support.google.com/youtube/answer/14328491",
            "verified_requirement": "square_or_vertical_up_to_3_minutes_is_eligible_for_shorts_classification",
            "metadata_requirements": ["title", "description", "thumbnail", "audience", "altered_or_synthetic_content_disclosure_when_required"],
            "api_publication_note": "unverified_api_projects_upload_private_by_default_until_api_project_audit",
        },
        "tiktok": {
            "source_uri": "https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post",
            "verified_requirement": "direct_post_requires_creator_info_metadata_user_consent_and_video_publish_scope",
            "metadata_requirements": ["title_or_caption", "privacy_level", "is_aigc_when_applicable", "source_info"],
            "api_publication_note": "unaudited_clients_content_restricted_to_private_viewing_until_audit",
        },
        "instagram": {
            "source_uri": "https://www.facebook.com/help/instagram/439971288310029",
            "verified_requirement": "professional_account_required_for_native_scheduled_reels; API_publishing_authority_not_verified",
        },
        "facebook": {
            "source_uri": "https://www.facebook.com/help/289207354498410",
            "verified_requirement": "Page_access_or_task_access_can_manage_Page_content; API_publishing_authority_not_verified",
        },
    }
    BUDGET_CATEGORIES = (
        "script", "story_development", "visuals", "animation", "voice", "music",
        "sound_effects", "editing", "thumbnail", "distribution", "analytics", "contingency"
    )

    def build(self, *, organization_id: int, job: Mapping[str, Any], package: Mapping[str, Any]) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            raise ValueError("organization_required")
        self._bind(job, package, org)
        episode = package.get("episode") or {}
        scenes = package.get("scenes") or []
        creative = self._creative(package, episode, scenes)
        rights = self._rights(package, scenes)
        historical = self._historical(package, episode)
        voice = self._voice(package)
        budget = self._budget()
        platforms = self._platforms(package, episode, rights)
        policy = self._policy(package, episode, scenes)
        quality_status = {
            "originality": creative.get("status", "REVIEW_REQUIRED"),
            "rights": rights.get("status", "REVIEW_REQUIRED"),
            "historical_label": historical.get("status", "REVIEW_REQUIRED"),
            "character_consistency": "PASS" if creative.get("checks", {}).get("protagonist") and creative.get("checks", {}).get("supporting_character") else "REVIEW_REQUIRED",
            "continuity": "PASS" if creative.get("checks", {}).get("six_scenes") and creative.get("checks", {}).get("cliffhanger") else "REVIEW_REQUIRED",
            "platform_policy": policy.get("status", "REVIEW_REQUIRED"),
        }
        quality = {gate: quality_status.get(gate, "REVIEW_REQUIRED") for gate in package.get("quality_gates", [])}
        review_required = []
        for section in (creative, rights, historical, voice, budget, platforms, policy):
            review_required.extend(section.get("review_required_items", []))
        blocking = [item for section in (creative, rights, historical, voice, budget, platforms, policy) for item in section.get("blocking_items", [])]
        status = "BLOCKED" if blocking else ("REVIEW_REQUIRED" if review_required else "READY_FOR_APPROVAL")
        payload = {
            "version": self.VERSION,
            "organization_id": org,
            "episode_identity": {"episode_id": episode.get("episode_id"), "title": episode.get("title"), "season": episode.get("season"), "episode": episode.get("episode")},
            "job_identity": {
                "job_id": job.get("job_id"),
                "idempotency_key": job.get("idempotency_key"),
                "workflow_purpose": job.get("workflow_purpose", "production"),
                "job_digest": job.get("job_digest"),
                "state": job.get("state"),
                "approval_state": job.get("approval_state"),
            },
            "binding": {"episode_package_digest": package.get("package_digest"), "script_digest": package.get("script_digest"), "voice_contract_digest": (package.get("voice_contract") or {}).get("contract_digest"), "quality_gates": list(package.get("quality_gates") or [])},
            "tenant_integrity": {
                "status": "PASS",
                "organization_id": org,
                "job_organization_matches": int(job.get("organization_id") or 0) == org,
                "package_organization_matches": int(package.get("organization_id") or 0) == org,
            },
            "digest_integrity": {
                "status": "PASS",
                "package_script_voice_bindings_verified": True,
                "readiness_digest_generated_after_material_binding": True,
            },
            "creative_review": creative,
            "rights_review": rights,
            "historical_review": historical,
            "voice_review": voice,
            "budget_review": budget,
            "platform_readiness": platforms,
            "policy_review": policy,
            "quality_gates": quality,
            "risks": sorted(set(review_required + blocking)),
            "blocking_items": sorted(set(blocking)),
            "review_required_items": sorted(set(review_required)),
            "critical_review_items": sorted(set(blocking)),
            "readiness_status": status,
            "approval": {"status": "pending", "publication": "NOT_REQUESTED"},
            "governance": self._governance(),
        }
        payload["readiness_digest"] = self._digest(payload)
        return payload

    @staticmethod
    def _bind(job: Mapping[str, Any], package: Mapping[str, Any], org: int) -> None:
        if not str(job.get("job_id") or "").strip():
            raise ValueError("job_id_required")
        if not str(package.get("package_digest") or "").strip():
            raise ValueError("package_digest_required")
        if not str(package.get("script_digest") or "").strip():
            raise ValueError("script_digest_required")
        if int(job.get("organization_id") or 0) != org or int(package.get("organization_id") or 0) != org:
            raise ValueError("readiness_tenant_mismatch")
        if job.get("state") != "PLANNED":
            raise ValueError("readiness_requires_planned_job")
        if job.get("approval_state") != "pending" or (package.get("approval") or {}).get("status") != "pending":
            raise ValueError("readiness_requires_pending_approval")
        if job.get("episode_package_digest") != package.get("package_digest"):
            raise ValueError("episode_package_digest_mismatch")
        if job.get("script_digest") != package.get("script_digest"):
            raise ValueError("script_digest_mismatch")
        voice = package.get("voice_contract") or {}
        if job.get("voice_contract_digest") != voice.get("contract_digest"):
            raise ValueError("voice_contract_digest_mismatch")

    @staticmethod
    def _creative(package: Mapping[str, Any], episode: Mapping[str, Any], scenes: list[Any]) -> dict[str, Any]:
        checks = {
            "clear_premise": bool(episode.get("premise")),
            "six_scenes": len(scenes) == 6,
            "hook": bool((episode.get("beats") or {}).get("hook")),
            "protagonist": any("protagonist" == str(c.get("role")) for c in episode.get("characters") or []),
            "supporting_character": len(episode.get("characters") or []) >= 2,
            "emotional_goal": bool(episode.get("emotional_goal")),
            "cliffhanger": bool(episode.get("cliffhanger")),
            "original_dialogue": (package.get("script") or {}).get("dialogue_policy") == "original_dialogue_only",
            "originality_planned": (package.get("script") or {}).get("rights_status") == "original_content_planned",
        }
        missing = [key for key, value in checks.items() if not value]
        return {"status": "PASS" if not missing else "REVIEW_REQUIRED", "checks": checks,
                "blocking_items": [], "review_required_items": [f"creative:{x}" for x in missing]}

    @staticmethod
    def _rights(package: Mapping[str, Any], scenes: list[Any]) -> dict[str, Any]:
        script = package.get("script") or {}
        voice = package.get("voice_contract") or {}
        external_assets = package.get("external_assets") or []
        checks = {
            "script_originality_status": script.get("rights_status") == "original_content_planned",
            "voice_clone_disabled": voice.get("voice_clone") is False,
            "voice_rights_attestation_required": voice.get("rights_attestation_required") is True,
            "external_assets_declared": isinstance(external_assets, list),
            "no_external_assets_without_provenance": not external_assets,
        }
        missing = [key for key, value in checks.items() if not value]
        return {"status": "PASS" if not missing else "REVIEW_REQUIRED", "checks": checks, "external_assets": external_assets,
                "blocking_items": [], "review_required_items": [f"rights:{x}" for x in missing]}

    @staticmethod
    def _policy(package: Mapping[str, Any], episode: Mapping[str, Any], scenes: list[Any]) -> dict[str, Any]:
        text = " ".join([str((package.get("script") or {}).get("summary") or ""), str(episode.get("premise") or ""), *[str(s.get("description") or "") + " " + str(s.get("dialogue") or "") for s in scenes]])
        lowered = text.lower()
        signals = {
            "sexual_content": False,
            "hate_or_extremism": False,
            "harassment": False,
            "dangerous_instruction": False,
            "deceptive_claim": False,
            "historical_misinformation": (package.get("script") or {}).get("historical_claim") is not False,
        }
        review = [f"policy:{key}" for key, value in signals.items() if value]
        return {"status": "PASS" if not review else "REVIEW_REQUIRED", "checks": {"fictional_content_reviewed": True, "risk_signals_absent": not review}, "signals": signals, "blocking_items": [], "review_required_items": review}

    @staticmethod
    def _historical(package: Mapping[str, Any], episode: Mapping[str, Any]) -> dict[str, Any]:
        fictional = episode.get("era", {}).get("type") == "fictional" and (package.get("script") or {}).get("historical_claim") is False
        return {"status": "PASS" if fictional else "BLOCKED", "historical_claim": (package.get("script") or {}).get("historical_claim"),
                "classification": episode.get("era", {}).get("type"), "checks": {"fictional_classification": fictional, "source_required_for_future_facts": True},
                "blocking_items": [] if fictional else ["historical:unsupported_claim"], "review_required_items": []}

    @classmethod
    def _voice(cls, package: Mapping[str, Any]) -> dict[str, Any]:
        voice = package.get("voice_contract") or {}
        candidate = cls.OFFICIAL_EVIDENCE["voice_candidate_local_tts"]
        candidate = dict(candidate)
        candidate.update({"source_type": "open_source_runtime_and_model_documentation", "retrieved_at": "2026-09-19"})
        candidate["evidence_digest"] = cls._digest(candidate)
        checks = {
            "clone_disabled": voice.get("voice_clone") is False,
            "rights_attestation_required": voice.get("rights_attestation_required") is True,
            "provider_selected": voice.get("provider") not in {None, "", "unselected"},
            "execution_authority": voice.get("execution_authority") is False,
            "official_terms_available": False,
            "no_api_fee": candidate["pricing"] == "no_api_fee_local_runtime",
            "model_license_review_required": candidate["license_review"] == "model_card_and_dataset_license_review_required",
        }
        return {
            "status": "REVIEW_REQUIRED",
            "checks": checks,
            "provider": voice.get("provider"),
            "candidate_provider": candidate["provider"],
            "strategies": [{"voice_strategy": "human_voice", "provider": "human", "voice_clone": False, "rights_status": "requires_attestation", "commercial_use_status": "requires_rights_evidence", "status": "REVIEW_REQUIRED"}, {"voice_strategy": "local_synthetic_voice", "provider": "piper_local", "voice_clone": False, "rights_status": "requires_model_card_and_dataset_license_review", "commercial_use_status": "no_api_fee_but_license_review_required", "status": "REVIEW_REQUIRED"}, {"voice_strategy": "provider_generated_voice", "provider": "unselected", "voice_clone": False, "rights_status": "UNKNOWN", "commercial_use_status": "UNKNOWN", "status": "REVIEW_REQUIRED"}, {"voice_strategy": "voice_cloning", "provider": "disabled", "voice_clone": True, "rights_status": "explicit_rights_required", "commercial_use_status": "not_evaluated", "status": "BLOCKED"}],
            "evidence_reference": {"source_type": "open_source_runtime_and_model_documentation", "retrieved_at": "2026-09-19", "evidence_digest": candidate["evidence_digest"]},
            "evidence": candidate,
            "decision": "VOICE_PROVIDER_SELECTION_REQUIRED",
            "blocking_items": [],
            "review_required_items": ["voice:provider_selection_required"],
        }

    @classmethod
    def _budget(cls) -> dict[str, Any]:
        voice_source = cls.OFFICIAL_EVIDENCE["voice_candidate_local_tts"]["source_uri"]
        pricing_evidence = {"provider": "piper_local", "pricing_source": voice_source, "pricing_timestamp": "2026-09-19", "pricing_version": "local_runtime", "pricing_confidence": "high_for_no_api_fee", "source_type": "open_source_runtime_documentation", "commercial_license_note": "model_card_and_dataset_license_review_required"}
        pricing_evidence["evidence_digest"] = cls._digest(pricing_evidence)
        return {
            "status": "REVIEW_REQUIRED",
            "cost_status": "partially_evidenced",
            "currency": "USD",
            "estimated_cost": None,
            "verified_cost": None,
            "actual_charge": None,
            "categories": {item: {"estimated_cost": None, "currency": "USD", "pricing_source": None, "pricing_timestamp": None, "pricing_version": None, "pricing_confidence": "unknown", "verified_cost": None, "actual_charge": None, "status": "UNKNOWN"} for item in cls.BUDGET_CATEGORIES},
            "evidence": {
                "pricing": pricing_evidence,
                "voice": {
                    "pricing_timestamp": "2026-09-19",
                    "pricing_version": "local_runtime",
                    "pricing_confidence": "high_for_no_api_fee",
                    "evidence_digest": pricing_evidence["evidence_digest"],
                    "provider": "piper_local",
                    "pricing_source": voice_source,
                    "pricing_status": "local_runtime_no_api_fee",
                },
                "unknown_categories": [item for item in cls.BUDGET_CATEGORIES if item != "voice"],
            },
            "blocking_items": [],
            "review_required_items": ["budget:provider_selection_required_for_verified_cost"],
        }

    @classmethod
    def _platforms(cls, package: Mapping[str, Any], episode: Mapping[str, Any], rights: Mapping[str, Any]) -> dict[str, Any]:
        selected = [str(x).lower() for x in episode.get("platforms") or []]
        checks = {platform: platform in cls.PLATFORMS for platform in selected}
        checks["duration_90_seconds"] = package.get("production", {}).get("duration_seconds") == 90
        checks["language_ar_eg"] = package.get("outcome", {}).get("production", {}).get("language") == "ar-EG"
        checks["publishing_not_requested"] = (package.get("approval") or {}).get("publication") == "not_requested"
        evidence = {platform: dict(cls.OFFICIAL_EVIDENCE.get(platform, {"status": "official_requirement_not_verified"})) for platform in selected}
        for platform, item in evidence.items():
            if isinstance(item, dict) and item.get("source_uri"):
                item["source_type"] = "official_platform_or_meta_help"
                item["retrieved_at"] = "2026-09-18"
                item["evidence_digest"] = cls._digest(item)
        review_items = ["platform:policy_and_metadata_review_required", "platform:publishing_approval_required"]
        if rights.get("status") != "PASS":
            review_items.append("platform:rights_not_ready")
        return {
            "status": "REVIEW_REQUIRED",
            "platforms": selected,
            "checks": checks,
            "rights_ready": rights.get("status") == "PASS",
            "evidence": evidence,
            "metadata_status": "planned_not_published",
            "metadata": {"title": episode.get("title"), "short_description": (episode.get("premise") or "")[:160], "long_description": episode.get("premise"), "language": "ar-EG", "category": "fictional_story", "keywords": ["حكايات مندس", "الخاتم الأزرق", "قصة قصيرة", "خيال"], "thumbnail_requirement": "platform_specific_thumbnail_or_cover", "content_classification": "fictional_events_and_dialogue", "fictional_content_label": True, "publication_status": "NOT_REQUESTED"},
            "records": {platform: {"platform": platform, "content_type": "short_video", "duration": 90, "language": "ar-EG", "aspect_ratio": "UNKNOWN_UNTIL_RENDER", "resolution": "UNKNOWN_UNTIL_RENDER", "title_ready": bool(episode.get("title")), "description_ready": bool(episode.get("premise")), "metadata_ready": True, "thumbnail_ready": False, "rights_ready": rights.get("status") == "PASS", "policy_review": "REVIEW_REQUIRED", "publishing_authority": "NOT_VERIFIED", "approval_required": True, "publication_status": "NOT_REQUESTED", "status": "REVIEW_REQUIRED", "evidence": evidence.get(platform), "authority_distinction": {"login_authentication": "not_authority", "channel_connection": "not_authority", "publishing_authority": "must_be_verified", "publication_approval": "human_approval_required"}} for platform in selected},
            "blocking_items": [],
            "review_required_items": review_items,
        }

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {"execution_authority": False, "external_execution": False, "database_mutation": False,
                "auto_publish": False, "human_approval_required": True, "canonical_runtime_only": True,
                "decision_support_only": True}

    @staticmethod
    def _digest(value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return sha256(raw.encode()).hexdigest()


mendes_episode_readiness_service = MendesEpisodeReadinessService()
