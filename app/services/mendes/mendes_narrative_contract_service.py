"""Versioned narrative contracts for governed Hikayat Mendes production."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from app.services.mendes.mendes_canonical_foundation_service import mendes_canonical_foundation_service


class MendesNarrativeContractService:
    VERSION = "1.0"
    STATES = ("DRAFT", "REVIEW", "APPROVED", "SUPERSEDED", "RETIRED")

    def build_season_arc(self, *, organization_id: int, world_id: str, season_id: str,
                         version: int, title: str, chronology: list[Mapping[str, Any]],
                         unresolved_threads: list[str] | None = None,
                         resolved_threads: list[str] | None = None) -> dict[str, Any]:
        self._base(organization_id, season_id, version, title)
        payload = {
            "schema": "kemet.mendes.season_arc.v1", "version": int(version),
            "organization_id": int(organization_id), "world_id": str(world_id),
            "season_id": str(season_id), "title": str(title).strip(),
            "chronology": [dict(x) for x in chronology],
            "unresolved_threads": [str(x)[:200] for x in (unresolved_threads or [])],
            "resolved_threads": [str(x)[:200] for x in (resolved_threads or [])],
            "status": "DRAFT",
        }
        return self._finalize(payload)

    def build_story_episode(self, *, organization_id: int, world_id: str,
                            season: Mapping[str, Any], story_id: str, episode_id: str,
                            version: int, title: str, fields: Mapping[str, Any]) -> dict[str, Any]:
        self._base(organization_id, story_id, version, title)
        self._exact(season, "season")
        characters = self._exact_refs(fields.get("characters") or [], "character")
        payload = {
            "schema": "kemet.mendes.story_episode.v1", "version": int(version),
            "organization_id": int(organization_id), "world_id": str(world_id),
            "season_id": season.get("season_id"), "season_version": int(season["version"]),
            "season_digest": str(season["digest"]), "story_id": str(story_id),
            "episode_id": str(episode_id), "title": str(title).strip(),
            "logline": str(fields.get("logline") or "").strip(),
            "premise": str(fields.get("premise") or "").strip(),
            "theme": str(fields.get("theme") or "").strip(),
            "audience": str(fields.get("audience") or "").strip(),
            "genre": str(fields.get("genre") or "").strip(),
            "tone": str(fields.get("tone") or "").strip(),
            "narrative_objective": str(fields.get("narrative_objective") or "").strip(),
            "characters": characters,
            "locations": list(fields.get("locations") or []),
            "conflict": str(fields.get("conflict") or "").strip(),
            "stakes": str(fields.get("stakes") or "").strip(),
            "beginning": str(fields.get("beginning") or "").strip(),
            "middle": str(fields.get("middle") or "").strip(),
            "ending": str(fields.get("ending") or "").strip(),
            "continuity_dependencies": list(fields.get("continuity_dependencies") or []),
            "canon_impact": list(fields.get("canon_impact") or []),
            "rights": self._rights(fields.get("rights")), "evidence": list(fields.get("evidence") or []),
            "status": "DRAFT",
        }
        return self._finalize(payload)

    def build_script(self, *, organization_id: int, episode: Mapping[str, Any],
                     version: int, scenes: list[Mapping[str, Any]],
                     dialogue: list[Mapping[str, Any]] | None = None,
                     narration: list[str] | None = None,
                     timing: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._exact(episode, "episode")
        self._base(organization_id, str(episode["episode_id"]), version, str(episode["title"]))
        payload = {
            "schema": "kemet.mendes.script.v1", "version": int(version),
            "organization_id": int(organization_id), "story_id": episode.get("story_id"),
            "episode_id": episode.get("episode_id"), "episode_version": int(episode["version"]),
            "episode_digest": str(episode["digest"]),
            "scenes": [self._exact_ref(x, "scene") for x in scenes],
            "dialogue": [dict(x) for x in (dialogue or [])],
            "narration": [str(x)[:3000] for x in (narration or [])],
            "action": list((timing or {}).get("action") or []),
            "character_references": self._exact_refs(episode.get("characters") or [], "character"),
            "locations": list(episode.get("locations") or []),
            "continuity_constraints": list(episode.get("continuity_dependencies") or []),
            "visual_direction": dict((timing or {}).get("visual_direction") or {}),
            "audio_direction": dict((timing or {}).get("audio_direction") or {}),
            "timing": dict(timing or {}), "rights_sensitive_elements": list((timing or {}).get("rights_sensitive_elements") or []),
            "classification": str((timing or {}).get("classification") or "fictional"), "evidence": list(episode.get("evidence") or []),
            "status": "DRAFT",
        }
        return self._finalize(payload)

    def build_scene_breakdown(self, *, organization_id: int, script: Mapping[str, Any],
                              version: int, scenes: list[Mapping[str, Any]]) -> dict[str, Any]:
        self._exact(script, "script")
        self._base(organization_id, str(script["episode_id"]), version, "Scene Breakdown")
        normalized = []
        for index, scene in enumerate(scenes, start=1):
            item = dict(scene)
            item["scene_id"] = str(item.get("scene_id") or f"{script['episode_id']}-sc{index}")
            item["sequence"] = index
            item["characters"] = [dict(x) if isinstance(x, Mapping) else str(x) for x in (item.get("characters") or [])]
            item["required_media"] = list(item.get("required_media") or [])
            item["production_status"] = str(item.get("production_status") or "PLANNED")
            item["quality_status"] = str(item.get("quality_status") or "REVIEW_REQUIRED")
            item["rights_status"] = str(item.get("rights_status") or "PENDING_REVIEW")
            normalized.append(item)
        payload = {
            "schema": "kemet.mendes.scene_breakdown.v1", "version": int(version),
            "organization_id": int(organization_id), "episode_id": script.get("episode_id"),
            "script_version": int(script["version"]), "script_digest": str(script["digest"]),
            "scenes": normalized, "status": "DRAFT",
        }
        return self._finalize(payload)

    def build_storyboard(self, *, organization_id: int, scene_breakdown: Mapping[str, Any],
                         version: int, shots: list[Mapping[str, Any]]) -> dict[str, Any]:
        self._exact(scene_breakdown, "scene_breakdown")
        self._base(organization_id, str(scene_breakdown["episode_id"]), version, "Storyboard")
        normalized = []
        for index, shot in enumerate(shots, start=1):
            item = dict(shot)
            item["shot_id"] = str(item.get("shot_id") or f"{scene_breakdown['episode_id']}-sh{index}")
            item["sequence"] = index
            item.setdefault("approval_state", "PENDING")
            item.setdefault("generated_asset_refs", [])
            normalized.append(item)
        payload = {
            "schema": "kemet.mendes.storyboard.v1", "version": int(version),
            "organization_id": int(organization_id), "episode_id": scene_breakdown.get("episode_id"),
            "scene_breakdown_version": int(scene_breakdown["version"]),
            "scene_breakdown_digest": str(scene_breakdown["digest"]), "shots": normalized,
            "status": "DRAFT",
        }
        return self._finalize(payload)

    def validate_continuity(self, *, character_versions: list[Mapping[str, Any]],
                            script: Mapping[str, Any], scene_breakdown: Mapping[str, Any],
                            storyboard: Mapping[str, Any]) -> dict[str, Any]:
        findings: list[dict[str, Any]] = []
        for char in character_versions:
            try:
                self._exact(char, "character")
            except ValueError as exc:
                findings.append({"code": "CHARACTER_BINDING_INVALID", "message": str(exc), "severity": "BLOCKED"})
        if str(scene_breakdown.get("script_digest")) != str(script.get("digest")):
            findings.append({"code": "SCRIPT_DIGEST_MISMATCH", "message": "scene breakdown is not bound to the exact script digest", "severity": "BLOCKED"})
        if str(storyboard.get("scene_breakdown_digest")) != str(scene_breakdown.get("digest")):
            findings.append({"code": "SCENE_BREAKDOWN_DIGEST_MISMATCH", "message": "storyboard is not bound to the exact scene breakdown digest", "severity": "BLOCKED"})
        for shot in storyboard.get("shots") or []:
            if not str(shot.get("scene_id") or "").strip():
                findings.append({"code": "SHOT_SCENE_REQUIRED", "message": "shot must identify an exact scene", "severity": "BLOCKED"})
        return {
            "schema": "kemet.mendes.continuity_report.v1", "status": "PASS" if not findings else "BLOCKED",
            "findings": findings, "machine_readable": True, "canonical_mutation": False,
            "execution_authority": False, "human_approval_required": True,
        }

    @staticmethod
    def _exact_ref(value: Mapping[str, Any], label: str) -> dict[str, Any]:
        if not isinstance(value, Mapping) or not value.get("digest") or not value.get("version"):
            raise ValueError(f"{label}_exact_binding_required")
        return {"id": value.get("id") or value.get(f"{label}_id") or value.get("scene_id"), "version": int(value["version"]), "digest": str(value["digest"])}

    def _exact_refs(self, values: list[Any], label: str) -> list[dict[str, Any]]:
        return [self._exact_ref(value, label) for value in values]

    @staticmethod
    def _exact(value: Mapping[str, Any], label: str) -> None:
        if not isinstance(value, Mapping) or not value.get("digest") or not value.get("version"):
            raise ValueError(f"{label}_exact_binding_required")

    @staticmethod
    def _rights(value: Any) -> dict[str, Any]:
        if isinstance(value, Mapping):
            return dict(value)
        return {"status": "UNKNOWN"}

    @staticmethod
    def _base(organization_id: int, identity: str, version: int, title: str) -> None:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        if not str(identity or "").strip():
            raise ValueError("identity_required")
        if int(version or 0) <= 0:
            raise ValueError("invalid_version")
        if not str(title or "").strip():
            raise ValueError("title_required")

    @staticmethod
    def _finalize(payload: dict[str, Any]) -> dict[str, Any]:
        payload["digest"] = mendes_canonical_foundation_service.digest(payload)
        payload["provenance"] = {"contract_version": "1.0", "source": "kemet_canonical_runtime", "exact_binding_required": True}
        payload["governance"] = {"execution_authority": False, "external_execution": False, "human_approval_required": True, "canonical_runtime_only": True}
        return payload


mendes_narrative_contract_service = MendesNarrativeContractService()
