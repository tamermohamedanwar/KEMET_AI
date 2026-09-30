
"""Canonical cinematic production planning, identity continuity, shot direction, and targeted regeneration."""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping


class CinematicProductionLayer:
    VERSION = "1.1"
    SCHEMAS = {
        "character_identity": "kemet.cinematic.character_identity.v2",
        "character_reference_plates": "kemet.cinematic.character_reference_plates.v1",
        "world_continuity": "kemet.cinematic.world_continuity.v2",
        "world_reference_plates": "kemet.cinematic.world_reference_plates.v1",
        "shot_plan": "kemet.cinematic.shot_plan.v2",
        "storyboard": "kemet.cinematic.storyboard.v1",
        "previs": "kemet.cinematic.previs.v1",
        "asset_manifest": "kemet.cinematic.asset_manifest.v1",
        "voice_sound": "kemet.cinematic.voice_sound.v1",
        "qa_report": "kemet.cinematic.qa_report.v1",
        "episode_graph": "kemet.cinematic.episode_graph.v1",
    }

    def production_memory(self, *, organization_id: int, project_id: str, characters: list[Mapping[str, Any]], worlds: list[Mapping[str, Any]], style: Mapping[str, Any] | None = None, voice_profiles: list[Mapping[str, Any]] | None = None, continuity_state: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        """Bind persistent identity/style/voice/continuity into one canonical production-state artifact."""
        self._org(organization_id)
        char_records = [self._memory_record(x, "character") for x in characters]
        world_records = [self._memory_record(x, "world") for x in worlds]
        voice_records = [self._memory_record(x, "voice") for x in (voice_profiles or [])]
        style_record = dict(style or {})
        if style_record and not style_record.get("digest"):
            style_record["digest"] = self._stable_digest(style_record)
        return self._finalize({
            "schema": "kemet.cinematic.production_memory.v1",
            "version": 1, "organization_id": int(organization_id), "project_id": str(project_id),
            "characters": char_records, "worlds": world_records, "style": style_record,
            "voices": voice_records, "continuity_state": [dict(x) for x in (continuity_state or [])],
            "canonical": True, "provider_independent": True,
            "policy": {"identity_persists_across_episodes": True, "world_persists_across_episodes": True,
                       "state_changes_require_version": True, "unapproved_outputs_are_noncanonical": True},
        })

    def continuity_impact(self, *, organization_id: int, changed_entity: Mapping[str, Any], downstream: list[Mapping[str, Any]]) -> dict[str, Any]:
        """Deterministically localize downstream artifacts affected by a canonical version change."""
        self._org(organization_id)
        entity_id = str(changed_entity.get("character_id") or changed_entity.get("world_id") or changed_entity.get("id") or "").strip()
        version = int(changed_entity.get("version") or 0)
        digest = str(changed_entity.get("digest") or "").strip()
        if not entity_id or version <= 0 or not digest:
            raise ValueError("changed_entity_exact_binding_required")
        affected, unaffected = [], []
        for item in downstream:
            ref_ids = set(str(x) for x in (item.get("character_ids") or []))
            if item.get("character_id"): ref_ids.add(str(item["character_id"]))
            if item.get("world_id"): ref_ids.add(str(item["world_id"]))
            refs = item.get("references") or []
            for ref in refs:
                if isinstance(ref, Mapping):
                    ref_ids.add(str(ref.get("id") or ""))
            if entity_id in ref_ids:
                affected.append(dict(item))
            else:
                unaffected.append(dict(item))
        return self._finalize({
            "schema": "kemet.cinematic.continuity_impact.v1", "version": 1,
            "organization_id": int(organization_id), "changed_entity": {"id": entity_id, "version": version, "digest": digest},
            "affected": affected, "unaffected": unaffected,
            "policy": {"regenerate_affected_only": True, "preserve_unaffected": True, "recompute_downstream_qa": True},
        })

    @staticmethod
    def _memory_record(value: Mapping[str, Any], kind: str) -> dict[str, Any]:
        if not isinstance(value, Mapping):
            raise ValueError(f"{kind}_memory_invalid")
        entity_id = str(value.get(f"{kind}_id") or value.get("id") or "").strip()
        digest = str(value.get("digest") or "").strip()
        version = int(value.get("version") or 0)
        if not entity_id or not digest or version <= 0:
            raise ValueError(f"{kind}_memory_exact_binding_required")
        return {"id": entity_id, "version": version, "digest": digest, "state": dict(value.get("state") or {}), "provenance": dict(value.get("provenance") or {})}

    @staticmethod
    def _stable_digest(value: Mapping[str, Any]) -> str:
        return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()

    def character_identity(self, *, organization_id: int, character: Mapping[str, Any], version: int) -> dict[str, Any]:
        self._org(organization_id)
        self._exact(character, "character")
        payload = {
            "schema": self.SCHEMAS["character_identity"], "version": int(version),
            "organization_id": int(organization_id),
            "character_id": character.get("character_id") or character.get("id"),
            "character_version": int(character["version"]),
            "character_digest": str(character["digest"]),
            "identity": dict(character.get("identity") or {}),
            "visual_identity": dict(character.get("visual_identity") or {}),
            "visual_bible": dict(character.get("visual_bible") or {}),
            "voice_profile": dict(character.get("voice_profile") or {}),
            "speech_style": dict(character.get("speech_style") or {}),
            "canonical_facts": list(character.get("canonical_facts") or []),
            "assets": list(character.get("assets") or []),
            "continuity": list(character.get("continuity") or []),
            "forbidden_drift": list((character.get("visual_bible") or {}).get("forbidden_variations") or []),
            "status": "CANONICAL_IDENTITY_BINDING",
        }
        return self._finalize(payload)

    def character_reference_plates(self, *, organization_id: int, character: Mapping[str, Any], plates: list[Mapping[str, Any]]) -> dict[str, Any]:
        self._org(organization_id); self._exact(character, "character")
        required = ("front", "profile", "three_quarter", "back", "full_body")
        normalized = {str(p.get("view")): dict(p) for p in plates if isinstance(p, Mapping) and p.get("view")}
        missing = [view for view in required if view not in normalized]
        if missing: raise ValueError("character_reference_plates_missing:" + ",".join(missing))
        for plate in normalized.values():
            if not plate.get("asset_id") or not plate.get("digest"):
                raise ValueError("character_reference_plate_exact_binding_required")
        return self._finalize({
            "schema": self.SCHEMAS["character_reference_plates"], "version": 1,
            "organization_id": int(organization_id),
            "character_id": character.get("character_id") or character.get("id"),
            "character_version": int(character["version"]), "character_digest": str(character["digest"]),
            "plates": normalized,
            "identity_invariants": {"face": True, "body_proportions": True, "hair": True,
                                    "wardrobe": True, "distinctive_features": True, "drift_requires_review": True},
            "reference_policy": "neutral_lighting_and_background_first", "provider_independent": True})

    def world_continuity(self, *, organization_id: int, world: Mapping[str, Any], version: int) -> dict[str, Any]:
        self._org(organization_id)
        self._exact(world, "world")
        payload = {
            "schema": self.SCHEMAS["world_continuity"], "version": int(version),
            "organization_id": int(organization_id), "world_id": world.get("world_id") or world.get("id"),
            "world_version": int(world["version"]), "world_digest": str(world["digest"]),
            "visual_style": dict(world.get("visual_style") or {}),
            "narrative_style": dict(world.get("narrative_style") or {}),
            "geography": dict(world.get("geography") or {}), "places": list(world.get("places") or []),
            "cultures": list(world.get("cultures") or []), "symbols": list(world.get("symbols") or []),
            "artifacts": list(world.get("artifacts") or []), "timeline": list(world.get("timeline") or []),
            "rules": list(world.get("rules") or []), "continuity_rules": list(world.get("continuity_rules") or []),
            "prohibited_contradictions": list(world.get("prohibited_contradictions") or []),
            "status": "CANONICAL_WORLD_BINDING",
        }
        return self._finalize(payload)

    def world_reference_plates(self, *, organization_id: int, world: Mapping[str, Any], plates: list[Mapping[str, Any]]) -> dict[str, Any]:
        self._org(organization_id); self._exact(world, "world")
        if not plates: raise ValueError("world_reference_plates_required")
        normalized = []
        for plate in plates:
            if not plate.get("view") or not plate.get("asset_id") or not plate.get("digest"):
                raise ValueError("world_reference_plate_exact_binding_required")
            normalized.append(dict(plate))
        return self._finalize({
            "schema": self.SCHEMAS["world_reference_plates"], "version": 1,
            "organization_id": int(organization_id), "world_id": world.get("world_id") or world.get("id"),
            "world_version": int(world["version"]), "world_digest": str(world["digest"]),
            "plates": normalized,
            "invariants": {"geography": True, "architecture": True, "lighting": True,
                           "materials": True, "props": True, "spatial_relationships": True,
                           "drift_requires_review": True},
            "provider_independent": True})

    def shot_plan(self, *, organization_id: int, scene: Mapping[str, Any], shots: list[Mapping[str, Any]],
                  character_bindings: list[Mapping[str, Any]], world_binding: Mapping[str, Any]) -> dict[str, Any]:
        self._org(organization_id)
        self._exact(world_binding, "world_binding")
        characters = [self._binding(x, "character") for x in character_bindings]
        normalized = []
        for index, raw in enumerate(shots, start=1):
            item = dict(raw)
            item["shot_id"] = str(item.get("shot_id") or f"{scene.get('scene_id','scene')}-sh{index}")
            item["sequence"] = index
            item["character_bindings"] = characters
            item["world_binding"] = self._binding(world_binding, "world")
            item["reference_asset_ids"] = list(item.get("reference_asset_ids") or [])
            item["shot_intent"] = dict(item.get("shot_intent") or {})
            item["camera"] = dict(item.get("camera") or {}) if isinstance(item.get("camera"), Mapping) else {"description": item.get("camera", "")}
            item["lens"] = item.get("lens")
            item["movement"] = item.get("movement") or "static"
            item["framing"] = item.get("framing") or "medium"
            item["duration_seconds"] = float(item.get("duration_seconds") or 0)
            item["transition"] = item.get("transition") or "cut"
            item["continuity_constraints"] = list(item.get("continuity_constraints") or [])
            item["generation_prompt_status"] = "DERIVE_FROM_CANONICAL_BINDINGS"
            normalized.append(item)
        payload = {
            "schema": self.SCHEMAS["shot_plan"], "version": 1, "organization_id": int(organization_id),
            "scene_id": scene.get("scene_id"), "scene_digest": scene.get("digest"), "shots": normalized,
            "cinematic_language": dict(scene.get("visual_direction") or {}),
            "continuity_policy": {"character_identity_locked": True, "world_locked": True, "shot_level_regeneration": True},
        }
        return self._finalize(payload)

    def storyboard(self, *, organization_id: int, project_id: str, scenes: list[Mapping[str, Any]], shots: list[Mapping[str, Any]], reference_pack: Mapping[str, Any]) -> dict[str, Any]:
        self._org(organization_id)
        self._exact(reference_pack, "reference_pack")
        panels = []
        for index, shot in enumerate(shots, start=1):
            panel = dict(shot)
            panel["panel_id"] = str(panel.get("panel_id") or f"panel-{index:03d}")
            panel["scene_id"] = panel.get("scene_id") or (scenes[index - 1].get("scene_id") if index <= len(scenes) else "scene-unknown")
            panel["story_beat"] = dict(panel.get("story_beat") or {})
            panel["composition"] = dict(panel.get("composition") or {})
            panel["camera"] = dict(panel.get("camera") or {})
            panel["lighting"] = dict(panel.get("lighting") or {})
            panel["characters"] = list(panel.get("characters") or [])
            panel["environment"] = dict(panel.get("environment") or {})
            panel["continuity_constraints"] = list(panel.get("continuity_constraints") or [])
            panels.append(panel)
        return self._finalize({
            "schema": self.SCHEMAS["storyboard"], "version": 1, "organization_id": int(organization_id),
            "project_id": str(project_id), "reference_pack_digest": reference_pack["digest"],
            "scenes": [dict(x) for x in scenes], "panels": panels,
            "panel_policy": {"one_panel_per_generation_intent": True, "references_are_canonical": True},
            "human_review_required": True})

    def previs(self, *, organization_id: int, project_id: str, storyboard: Mapping[str, Any],
               camera_plan: list[Mapping[str, Any]], blocking: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        self._org(organization_id); self._exact(storyboard, "storyboard")
        frames = []
        for index, shot in enumerate(camera_plan, start=1):
            frame = dict(shot)
            frame["previs_frame_id"] = str(frame.get("previs_frame_id") or f"previs-{index:03d}")
            frame["shot_id"] = frame.get("shot_id") or f"shot-{index:03d}"
            frame["blocking"] = dict((blocking or [{}])[index - 1] if index <= len(blocking or []) else {})
            frame["camera_validation"] = {"framing_locked": True, "movement_declared": bool(frame.get("movement"))}
            frames.append(frame)
        return self._finalize({
            "schema": self.SCHEMAS["previs"], "version": 1, "organization_id": int(organization_id),
            "project_id": str(project_id), "storyboard_digest": storyboard["digest"],
            "frames": frames, "blocking": [dict(x) for x in (blocking or [])],
            "purpose": "validate_composition_camera_blocking_before_expensive_generation",
            "human_review_required": True})

    def asset_manifest(self, *, organization_id: int, episode_id: str, assets: list[Mapping[str, Any]]) -> dict[str, Any]:
        self._org(organization_id)
        normalized = []
        for asset in assets:
            item = dict(asset)
            item["asset_id"] = str(item.get("asset_id") or item.get("id") or "").strip()
            if not item["asset_id"]: raise ValueError("asset_id_required")
            item["character_ids"] = list(item.get("character_ids") or [])
            item["world_id"] = item.get("world_id")
            item["reference_of"] = item.get("reference_of")
            item["sha256"] = item.get("sha256")
            item["rights_status"] = str(item.get("rights_status") or "PENDING_REVIEW")
            normalized.append(item)
        return self._finalize({"schema": self.SCHEMAS["asset_manifest"], "version": 1,
            "organization_id": int(organization_id), "episode_id": str(episode_id), "assets": normalized,
            "identity_policy": {"reuse_canonical_references": True, "drift_requires_review": True}})

    def voice_sound(self, *, organization_id: int, episode_id: str, characters: list[Mapping[str, Any]],
                    narrator: Mapping[str, Any] | None = None, music: list[Mapping[str, Any]] | None = None,
                    sfx: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        self._org(organization_id)
        bindings = []
        for char in characters:
            self._exact(char, "character")
            bindings.append({"character_id": char.get("character_id") or char.get("id"),
                             "character_digest": char["digest"], "voice_profile": dict(char.get("voice_profile") or {})})
        return self._finalize({"schema": self.SCHEMAS["voice_sound"], "version": 1,
            "organization_id": int(organization_id), "episode_id": str(episode_id),
            "character_voices": bindings, "narrator": dict(narrator or {}),
            "music": [dict(x) for x in (music or [])], "sfx": [dict(x) for x in (sfx or [])],
            "continuity_policy": {"voice_identity_locked": True, "music_motifs_persist": True}})

    def qa(self, *, organization_id: int, episode_graph: Mapping[str, Any], findings: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        self._org(organization_id)
        findings_out = [dict(x) for x in (findings or [])]
        required = ["character_drift", "visual_inconsistency", "bad_arabic_text", "lip_audio_timing",
                     "voice_clarity", "scene_continuity", "frame_quality", "pacing", "missing_assets"]
        checks = {name: "PASS" for name in required}
        for item in findings_out:
            code = str(item.get("code") or "")
            if code in checks: checks[code] = "FAIL"
        status = "PASS" if all(v == "PASS" for v in checks.values()) else "FAIL"
        return self._finalize({"schema": self.SCHEMAS["qa_report"], "version": 1,
            "organization_id": int(organization_id), "episode_graph_digest": episode_graph.get("digest"),
            "status": status, "checks": checks, "findings": findings_out,
            "regeneration_policy": {"mode": "targeted", "scope": "failed_asset_or_shot_only", "whole_episode_regeneration": False}})

    def episode_graph(self, *, organization_id: int, episode: Mapping[str, Any], world_binding: Mapping[str, Any],
                      characters: list[Mapping[str, Any]], scenes: list[Mapping[str, Any]],
                      shots: list[Mapping[str, Any]], assets: list[Mapping[str, Any]], voice_sound: Mapping[str, Any]) -> dict[str, Any]:
        self._org(organization_id)
        self._exact(world_binding, "world_binding")
        character_bindings = [self._binding(c, "character") for c in characters]
        payload = {"schema": self.SCHEMAS["episode_graph"], "version": self.VERSION,
            "organization_id": int(organization_id), "episode_id": episode.get("episode_id"),
            "episode_digest": episode.get("digest"), "world": self._binding(world_binding, "world"),
            "characters": character_bindings, "scenes": [dict(x) for x in scenes],
            "shots": [dict(x) for x in shots], "assets": [dict(x) for x in assets],
            "voice_sound": dict(voice_sound),
            "execution_graph": ["episode_specification", "storyboard", "asset_generation", "voice_generation",
                                 "render", "cinematic_qa", "targeted_regeneration", "human_approval"],
            "generation_policy": {"prompts_are_derived_artifacts": True, "canonical_identity_required": True,
                                   "human_approval_required": True, "external_execution": False},}
        return self._finalize(payload)

    @staticmethod
    def _binding(value: Mapping[str, Any], label: str) -> dict[str, Any]:
        if not isinstance(value, Mapping) or not value.get("digest") or not value.get("version"):
            raise ValueError(f"{label}_exact_binding_required")
        return {"id": value.get("character_id") or value.get("world_id") or value.get("id"),
                "version": int(value["version"]), "digest": str(value["digest"])}

    @staticmethod
    def _exact(value: Mapping[str, Any], label: str) -> None:
        if not isinstance(value, Mapping) or not value.get("digest") or not value.get("version"):
            raise ValueError(f"{label}_exact_binding_required")

    @staticmethod
    def _org(value: Any) -> None:
        if int(value or 0) <= 0: raise ValueError("organization_required")

    @staticmethod
    def _finalize(payload: dict[str, Any]) -> dict[str, Any]:
        payload["digest"] = sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()
        payload["provenance"] = {"source": "kemet_canonical_runtime", "version": "1.0"}
        payload["governance"] = {"execution_authority": False, "external_execution": False, "human_approval_required": True, "mcp": False}
        return payload

    @staticmethod
    def build_generation_prompt(*, shot: Mapping[str, Any], character_bindings: list[Mapping[str, Any]], world_binding: Mapping[str, Any]) -> str:
        """Derive a provider-facing prompt from canonical bindings; do not accept it as canon."""
        chars = ", ".join(str(x.get("id")) for x in character_bindings)
        return (f"SHOT {shot.get('shot_id')}. Canonical characters: {chars}. "
                f"World binding: {world_binding.get('id')} v{world_binding.get('version')}. "
                f"Action: {shot.get('action','')}. Camera: {shot.get('camera','')}. "
                f"Lighting: {shot.get('lighting','')}. Emotion: {shot.get('emotion','')}. "
                "Preserve exact canonical identity and world continuity. Do not invent identity changes.")


cinematic_production_layer = CinematicProductionLayer()
