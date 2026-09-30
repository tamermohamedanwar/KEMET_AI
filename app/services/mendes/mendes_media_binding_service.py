from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from app.core.media.contracts import (
    ASSET_PLAN,
    CONTENT_BLUEPRINT,
    CONTENT_INTENT,
    RENDER_PLAN,
    SCENE_PLAN,
    VOICE_PLAN,
    build_contract,
)


class MendesMediaBindingService:
    VERSION = "1.0"

    def bind(self, *, organization_id: int, episode_package: Mapping[str, Any]) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            raise ValueError("organization_required")
        if not isinstance(episode_package, Mapping):
            raise ValueError("episode_package_required")
        if int(episode_package.get("organization_id") or 0) != org:
            raise ValueError("episode_package_tenant_mismatch")
        package_digest = str(episode_package.get("package_digest") or "").strip()
        if not package_digest:
            raise ValueError("episode_package_digest_required")
        episode = episode_package.get("episode")
        scenes = episode_package.get("scenes")
        script = episode_package.get("script")
        voice = episode_package.get("voice_contract")
        if not isinstance(episode, Mapping) or not episode.get("episode_id"):
            raise ValueError("episode_identity_required")
        if not isinstance(scenes, list) or not scenes:
            raise ValueError("scenes_required")
        if not isinstance(script, Mapping) or not episode_package.get("script_digest"):
            raise ValueError("script_binding_required")
        if not isinstance(voice, Mapping) or not voice.get("contract_digest"):
            raise ValueError("voice_binding_required")
        approval = episode_package.get("approval") or {}
        if approval.get("required") is not True or approval.get("status") != "pending":
            raise ValueError("human_approval_required")
        execution = episode_package.get("execution") or {}
        if execution.get("automatic") is not False or execution.get("external_execution") is not False:
            raise ValueError("execution_governance_required")

        episode_id = str(episode["episode_id"])
        title = str(episode.get("title") or "").strip()[:200]
        intent = build_contract(
            CONTENT_INTENT, organization_id=org,
            contract_id=f"mendes-intent-{episode_id}",
            payload={"world": "Mendes World", "series": "Hikayat Mendes", "episode_id": episode_id,
                     "title": title, "language": str(script.get("language") or "ar-EG"),
                     "purpose": "controlled_pilot_episode", "source_package_digest": package_digest},
        )
        blueprint = build_contract(
            CONTENT_BLUEPRINT, organization_id=org,
            contract_id=f"mendes-blueprint-{episode_id}",
            payload={"intent_digest": intent["digest"], "episode_id": episode_id,
                     "classification": script.get("classification"), "historical_claim": script.get("historical_claim"),
                     "characters": episode.get("characters") or [], "source_package_digest": package_digest},
        )
        scene_payload = [{"scene_number": i, "description": str(s.get("description") or "").strip(),
                          "characters": list(s.get("characters") or []),
                          "visual_prompt": str(s.get("visual_prompt") or "").strip(),
                          "dialogue": str(s.get("dialogue") or "").strip(),
                          "duration_seconds": int(s.get("duration_seconds") or 0)}
                         for i, s in enumerate(scenes, 1)]
        if any(not item["description"] or item["duration_seconds"] <= 0 for item in scene_payload):
            raise ValueError("invalid_scene_plan")
        scene = build_contract(
            SCENE_PLAN, organization_id=org,
            contract_id=f"mendes-scenes-{episode_id}",
            payload={"blueprint_digest": blueprint["digest"], "episode_id": episode_id, "scenes": scene_payload},
        )
        assets = build_contract(
            ASSET_PLAN, organization_id=org,
            contract_id=f"mendes-assets-{episode_id}",
            payload={"scene_plan_digest": scene["digest"], "episode_id": episode_id,
                     "assets": [{"scene_number": x["scene_number"], "type": "image", "status": "provider_ready",
                                  "provenance_required": True, "copyright_style": "original"} for x in scene_payload]},
        )
        voice_plan = build_contract(
            VOICE_PLAN, organization_id=org,
            contract_id=f"mendes-voice-{episode_id}",
            payload={"script_digest": str(episode_package["script_digest"]), "episode_id": episode_id,
                     "language": str(voice.get("language") or script.get("language") or "ar-EG"),
                     "provider": voice.get("provider"), "voice_clone": voice.get("voice_clone") is True,
                     "rights_attestation_required": voice.get("rights_attestation_required") is True,
                     "status": voice.get("status"), "provider_output_trust": "untrusted"},
        )
        render = build_contract(
            RENDER_PLAN, organization_id=org,
            contract_id=f"mendes-render-{episode_id}",
            payload={"episode_id": episode_id, "scene_plan_digest": scene["digest"],
                     "asset_plan_digest": assets["digest"], "voice_plan_digest": voice_plan["digest"],
                     "duration_seconds": sum(x["duration_seconds"] for x in scene_payload),
                     "renderer": "ffmpeg-local", "status": "blocked_until_real_assets_and_approval"},
        )
        contracts = {"content_intent": intent, "content_blueprint": blueprint, "scene_plan": scene,
                     "asset_plan": assets, "voice_plan": voice_plan, "render_plan": render}
        binding = {"version": self.VERSION, "organization_id": org, "episode_id": episode_id,
                   "source_package_digest": package_digest,
                   "contract_digests": {k: v["digest"] for k, v in contracts.items()},
                   "governance": self._governance()}
        binding["binding_digest"] = self._digest(binding)
        return {"success": True, "status": "media_contracts_bound", "binding": binding, "contracts": contracts}

    @staticmethod
    def _digest(value: Any) -> str:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
        return sha256(raw.encode()).hexdigest()

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {"read_only": True, "advisory": True, "execution_authority": False,
                "external_execution": False, "auto_publish": False, "human_approval_required": True,
                "canonical_runtime_only": True, "mcp": False}


mendes_media_binding_service = MendesMediaBindingService()
