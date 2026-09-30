from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from typing import Any, Mapping

from app.core.media.provider_adapter_contract import MediaProviderAdapterDescriptor, validate_provider_output
from app.services.piper_tts_service import piper_tts_service
from app.core.media.google_veo_provider import google_veo_provider
from app.core.media.open_video_catalog import catalog_snapshot
from app.services.wan_backend_adapter import wan_backend_adapter


@dataclass(frozen=True)
class ProviderSpec:
    provider_id: str
    capabilities: tuple[str, ...]
    credential_env: str | None
    model: str
    source: str
    configured: bool


class CinematicProviderFabric:
    VERSION = "1.0"
    SCHEMA = "kemet.cinematic.provider_fabric.v1"

    def snapshot(self, organization_id: int | None) -> dict[str, Any]:
        specs = self._specs()
        return {
            "version": self.VERSION,
            "schema": self.SCHEMA,
            "organization_id": organization_id,
            "providers": [self._spec_snapshot(x) for x in specs],
            "open_source_video_catalog": catalog_snapshot(),
            "governance": self._governance(),
        }

    def build_episode_jobs(
        self,
        *,
        organization_id: int,
        cinematic: Mapping[str, Any],
        episode_id: str,
    ) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            return self._blocked("organization_required")
        if not episode_id.strip():
            return self._blocked("episode_id_required")
        if not isinstance(cinematic, Mapping):
            return self._blocked("cinematic_package_required")
        shots = list(cinematic.get("shots") or [])
        if not shots:
            return self._blocked("shots_required")

        provider_snapshot = self.snapshot(org)
        jobs = []
        for shot in shots:
            canonical_shot = self._canonicalize_shot(shot)
            jobs.append(self._shot_job(org, episode_id, canonical_shot))

        payload = {
            "version": self.VERSION,
            "schema": self.SCHEMA,
            "organization_id": org,
            "episode_id": episode_id,
            "provider_snapshot": provider_snapshot,
            "jobs": jobs,
            "approval": {
                "required": True,
                "status": "pending",
                "execution_requested": False,
            },
            "execution": {
                "automatic": False,
                "external_execution": False,
                "network": "disabled_until_approval",
            },
            "governance": self._governance(),
        }
        payload["job_graph_digest"] = self._digest(payload)
        return {"success": True, "status": "provider_jobs_ready", "fabric": payload}

    def _canonicalize_shot(self, shot: Mapping[str, Any]) -> dict[str, Any]:
        item = dict(shot)
        canonical_fields = (
            "shot_id", "sequence", "action", "camera", "lens", "framing", "movement",
            "lighting", "time", "emotion", "dialogue", "transition", "duration_seconds",
            "character_bindings", "world_binding", "reference_asset_ids",
        )
        canonical = {key: item.get(key) for key in canonical_fields}
        canonical["canonical_shot_digest"] = self._digest(canonical)
        item["canonical_shot_digest"] = canonical["canonical_shot_digest"]
        item["provider_prompt"] = self._derive_shot_prompt(item)
        item["generation_prompt_status"] = "DERIVED_FROM_CANONICAL_BINDINGS"
        return item

    def _shot_job(self, organization_id: int, episode_id: str, shot: Mapping[str, Any]) -> dict[str, Any]:
        shot_id = str(shot.get("shot_id") or "").strip()
        prompt = self._derive_shot_prompt(shot)
        if not shot_id or not prompt:
            return {
                "status": "blocked",
                "error": "canonical_shot_binding_required",
                "execution_authority": False,
            }

        image_provider = self._select("IMAGE_GENERATION")
        video_provider = self._select("VIDEO_GENERATION")
        voice = piper_tts_service.snapshot(organization_id)

        image_job = self._provider_job(
            organization_id=organization_id,
            episode_id=episode_id,
            shot_id=shot_id,
            stage="reference_image",
            provider=image_provider,
            prompt=prompt,
            input_refs=shot.get("reference_asset_ids") or [],
        )
        video_job = self._provider_job(
            organization_id=organization_id,
            episode_id=episode_id,
            shot_id=shot_id,
            stage="motion_video",
            provider=video_provider,
            prompt=prompt,
            input_refs=shot.get("reference_asset_ids") or [],
        )
        voice_job = {
            "stage": "voice",
            "provider_id": voice.get("provider_id"),
            "model": os.getenv("KEMET_TTS_MODEL_ID", "UNSELECTED_ARABIC_VOICE"),
            "target_locale": "ar-EG",
            "provider_locale": voice.get("language"),
            "configured": bool(voice.get("configured")),
            "quality_status": "NOT_QUALIFIED_FOR_EGYPTIAN_DIALECT",
            "execution_authority": False,
            "external_execution": False,
        }
        return {
            "shot_id": shot_id,
            "canonical_binding": {
                "character_ids": list(shot.get("character_ids") or []),
                "world_id": shot.get("world_id"),
                "reference_ids": list(shot.get("references") or []),
            },
            "image": image_job,
            "video": video_job,
            "voice": voice_job,
            "qa": {"required": True, "mode": "targeted", "whole_episode_regeneration": False},
        }

    @staticmethod
    def _derive_shot_prompt(shot: Mapping[str, Any]) -> str:
        parts = [
            str(shot.get("action") or "").strip(),
            f"emotion: {shot.get('emotion')}",
            f"camera: {shot.get('camera')}",
            f"lens: {shot.get('lens')}",
            f"framing: {shot.get('framing')}",
            f"movement: {shot.get('movement')}",
            f"lighting: {shot.get('lighting')}",
            f"time: {shot.get('time')}",
            f"dialogue: {shot.get('dialogue')}",
        ]
        character_ids = [str(x.get("id")) for x in (shot.get("character_bindings") or []) if x.get("id")]
        world = shot.get("world_binding") or {}
        refs = [str(x) for x in (shot.get("reference_asset_ids") or [])]
        if character_ids:
            parts.append("canonical characters: " + ", ".join(character_ids))
        if world.get("id"):
            parts.append(f"canonical world: {world.get('id')}")
        if refs:
            parts.append("reference assets: " + ", ".join(refs))
        parts.append("preserve canonical character identity, world continuity, wardrobe, proportions, and approved references")
        return "; ".join(x for x in parts if x and x != "emotion: None" and x != "camera: None")

    def _provider_job(
        self,
        *,
        organization_id: int,
        episode_id: str,
        shot_id: str,
        stage: str,
        provider: Mapping[str, Any],
        prompt: str,
        input_refs: list[Any],
    ) -> dict[str, Any]:
        configured = bool(provider.get("configured"))
        status = "ready_for_human_approval" if configured else "provider_not_configured"
        return {
            "stage": stage,
            "provider_id": provider.get("provider_id"),
            "model": provider.get("model"),
            "configured": configured,
            "status": status,
            "request": {
                "organization_id": organization_id,
                "episode_id": episode_id,
                "shot_id": shot_id,
                "prompt_digest": self._digest({"prompt": prompt}),
                "prompt_source": "kemet_canonical_binding",
                "reference_inputs": list(input_refs),
            },
            "execution": {
                "automatic": False,
                "approval_required": True,
                "external_execution": False,
                "execution_authority": False,
            },
        }

    def provider_preflight(self) -> dict[str, Any]:
        google = google_veo_provider.preflight()
        wan = wan_backend_adapter.preflight()
        return {
            "video": google,
            "video_candidates": [google, wan],
            "voice": piper_tts_service.snapshot(None),
            "governance": self._governance(),
        }

    def execute_approved_video_shot(self, *, organization_id: int, episode_id: str, shot: Mapping[str, Any], approval: Mapping[str, Any], output_path: str) -> dict[str, Any]:
        return google_veo_provider.generate_shot(
            organization_id=organization_id,
            episode_id=episode_id,
            shot=shot,
            approval=approval,
            output_path=output_path,
        )

    def _select(self, capability: str) -> dict[str, Any]:
        candidates = [x for x in self._specs() if capability in x.capabilities]
        if not candidates:
            return {"provider_id": None, "configured": False, "status": "no_provider"}
        item = candidates[0]
        return {
            "provider_id": item.provider_id,
            "model": item.model,
            "configured": item.configured,
            "credential_env": item.credential_env,
            "source": item.source,
        }
    def _specs(self) -> tuple[ProviderSpec, ...]:
        return (
            ProviderSpec(
                "google_nano_banana_2",
                ("IMAGE_GENERATION",),
                "GEMINI_API_KEY",
                "gemini-3.1-flash-image",
                "official_google_gemini_api",
                bool(os.getenv("GEMINI_API_KEY")),
            ),
            ProviderSpec(
                "google_veo_3_1",
                ("VIDEO_GENERATION",),
                "GEMINI_API_KEY",
                "veo-3.1-generate-preview",
                "official_google_gemini_api",
                bool(os.getenv("GEMINI_API_KEY")),
            ),
            ProviderSpec(
                "piper_local",
                ("TEXT_TO_SPEECH",),
                "KEMET_PIPER_EXECUTABLE",
                os.getenv("KEMET_TTS_MODEL_ID", "UNSELECTED_ARABIC_VOICE"),
                "local_open_source_runtime",
                bool(piper_tts_service.snapshot(None).get("configured")),
            ),
        )

    @staticmethod
    def _spec_snapshot(item: ProviderSpec) -> dict[str, Any]:
        descriptor = MediaProviderAdapterDescriptor(
            provider_id=item.provider_id,
            capabilities=item.capabilities,
        )
        return {
            **descriptor.snapshot(),
            "model": item.model,
            "source": item.source,
            "configured": item.configured,
            "credential_env": item.credential_env,
        }

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {
            "read_only": True,
            "execution_authority": False,
            "external_execution": False,
            "automatic_generation": False,
            "human_approval_required": True,
            "canonical_runtime_only": True,
            "mcp": False,
        }

    @staticmethod
    def _digest(value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return sha256(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _blocked(error: str) -> dict[str, Any]:
        return {
            "success": False,
            "status": "blocked",
            "error": error,
            "governance": CinematicProviderFabric._governance(),
        }


cinematic_provider_fabric = CinematicProviderFabric()
