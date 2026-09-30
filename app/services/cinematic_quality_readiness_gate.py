"""Provider-independent cinematic quality/readiness gate."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping


class CinematicQualityReadinessGate:
    SCHEMA = "kemet.cinematic.quality_readiness_gate.v1"
    REQUIRED = (
        "story", "character_identity", "world_continuity", "shot_direction",
        "animation_motion", "asset_references", "voice_dialogue", "music_sfx",
        "arabic_text_localization", "editing_pacing", "render_integrity",
        "cinematic_qa", "provenance", "human_approval",
    )

    @staticmethod
    def _digest(payload: Mapping[str, Any]) -> str:
        return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()

    def evaluate(self, *, organization_id: int, project_id: str, evidence: Mapping[str, Any], production_profile: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        if not project_id:
            raise ValueError("project_required")
        profile = dict(production_profile or {})
        if profile and profile.get("schema") != "kemet.visual.production_profile.v1":
            raise ValueError("production_profile_invalid")
        profile_dimensions = [str(x) for x in profile.get("qa_dimensions", []) if str(x)]
        checks = []
        for key in self.REQUIRED:
            value = evidence.get(key)
            ok = bool(value.get("verified")) if isinstance(value, Mapping) else bool(value)
            checks.append({"gate": key, "verified": ok, "required_by_profile": key in profile_dimensions})
        profile_checks = []
        for key in profile_dimensions:
            value = evidence.get(key)
            ok = bool(value.get("verified")) if isinstance(value, Mapping) else bool(value)
            profile_checks.append({"gate": key, "verified": ok, "profile_required": True})
        ready = all(item["verified"] for item in checks) and all(item["verified"] for item in profile_checks)
        payload = {
            "schema": self.SCHEMA, "version": 1,
            "organization_id": int(organization_id), "project_id": str(project_id),
            "status": "READY" if ready else "BLOCKED", "production_ready": ready,
            "checks": checks,
            "profile_checks": profile_checks,
            "production_profile": profile,
            "quality_contract": {
                "provider_independent": True,
                "targeted_regeneration": True,
                "canonical_references_required": True,
                "human_approval_required": True,
                "arabic_text_must_be_post_composited_or_verified": True,
                "audio_visual_sync_required": True,
                "motion_continuity_required": True,
            },
            "canonical_state_mutation": False, "execution_authority": False,
            "external_execution": False, "mcp": False, "fail_closed": True,
        }
        payload["digest"] = self._digest(payload)
        return payload


cinematic_quality_readiness_gate = CinematicQualityReadinessGate()
