from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from app.services.cinematic_production_layer import cinematic_production_layer
from app.services.mendes.mendes_canonical_foundation_service import mendes_canonical_foundation_service


class MendesCinematicOrchestrator:
    VERSION = "1.0"

    def build(self, *, organization_id: int, episode: Mapping[str, Any], scenes: list[Mapping[str, Any]],
              voice_contract: Mapping[str, Any]) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            raise ValueError("organization_required")
        episode_id = str(episode.get("episode_id") or "").strip()
        if not episode_id:
            raise ValueError("episode_id_required")
        characters = self._character_bibles(org, episode.get("characters") or [])
        world = self._world_bible(org)
        world_binding = cinematic_production_layer.world_continuity(
            organization_id=org, world=world, version=1
        )
        character_bindings = [
            cinematic_production_layer.character_identity(organization_id=org, character=c, version=1)
            for c in characters
        ]
        normalized_scenes = [self._scene(scene, episode_id, index) for index, scene in enumerate(scenes, 1)]
        shot_plans = []
        all_shots = []
        for scene in normalized_scenes:
            shots = [self._shot(scene)]
            plan = cinematic_production_layer.shot_plan(
                organization_id=org, scene=scene, shots=shots,
                character_bindings=character_bindings, world_binding=world_binding,
            )
            shot_plans.append(plan)
            all_shots.extend(plan["shots"])
        assets = self._reference_assets(episode_id, characters, world)
        asset_manifest = cinematic_production_layer.asset_manifest(
            organization_id=org, episode_id=episode_id, assets=assets
        )
        voice_sound = cinematic_production_layer.voice_sound(
            organization_id=org, episode_id=episode_id, characters=characters,
            narrator={"language": "ar-EG", "identity_status": "REVIEW_REQUIRED", "reason": "provider_voice_must_match_target_locale"},
            music=[{"music_id": "mendes-mystery-main", "motif": "blue-ring-mystery", "continuity": "canonical"}],
            sfx=[{"sfx_id": "mendes-stone-mechanism", "category": "stone_mechanism", "continuity": "canonical"}],
        )
        graph = cinematic_production_layer.episode_graph(
            organization_id=org, episode=episode, world_binding=world_binding,
            characters=characters, scenes=normalized_scenes, shots=all_shots,
            assets=asset_manifest["assets"], voice_sound=voice_sound,
        )
        prompts = [
            {"shot_id": shot["shot_id"], "prompt": cinematic_production_layer.build_generation_prompt(
                shot=shot, character_bindings=character_bindings, world_binding=world_binding
            )}
            for shot in all_shots
        ]
        qa = cinematic_production_layer.qa(organization_id=org, episode_graph=graph)
        return {
            "schema": "kemet.mendes.cinematic_episode_package.v1",
            "version": self.VERSION,
            "episode_id": episode_id,
            "world_canonical": world,
            "world_binding": world_binding,
            "characters_canonical": characters,
            "character_bindings": character_bindings,
            "scenes": normalized_scenes,
            "shot_plans": shot_plans,
            "shots": all_shots,
            "asset_manifest": asset_manifest,
            "voice_sound": voice_sound,
            "generation_prompts": prompts,
            "episode_graph": graph,
            "qa": qa,
            "voice_contract_binding": {"contract_digest": voice_contract.get("contract_digest"), "provider": voice_contract.get("provider"), "target_locale": "ar-EG"},
            "governance": {"human_approval_required": True, "external_execution": False, "execution_authority": False, "mcp": False, "prompts_are_derived_artifacts": True},
        }

    @staticmethod
    def _world_bible(org: int) -> dict[str, Any]:
        return mendes_canonical_foundation_service.build_world_bible(
            organization_id=org, world_id="mendes-world", version=1,
            title="Mendes World", status="CANONICAL",
            fields={
                "language": "ar-EG",
                "visual_style": {"medium": "original cinematic animation", "palette": "warm earth with controlled blue mystery accent", "camera": "cinematic naturalism", "lighting": "motivated practical light", "composition": "story-first, grounded, expressive"},
                "narrative_style": {"tone": "mystery, wonder, family stakes", "dialogue": "original Egyptian Arabic", "historical_mode": "fictional"},
                "places": [{"id": "mendes-gate", "name": "Mendes Gate", "status": "canonical"}],
                "rules": ["fictional_story_world", "no_unverified_historical_claims_presented_as_fact", "character_identity_persists_across_episodes"],
                "continuity_rules": ["wardrobe_and_proportions_persist", "locations_keep_visual_logic", "props_keep_state", "unresolved_mysteries_persist"],
                "prohibited_contradictions": ["character_identity_drift", "unexplained_wardrobe_change", "location_geometry_drift", "canon_event_reversal_without_story_reason"],
            },
        )

    @staticmethod
    def _character_bibles(org: int, values: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
        output = []
        for value in values:
            visual = str(value.get("visual_identity") or "original consistent Egyptian character design")
            voice = str(value.get("voice_profile") or "natural Egyptian Arabic")
            output.append(mendes_canonical_foundation_service.build_character_bible(
                organization_id=org, world_id="mendes-world",
                character_id=str(value.get("character_id") or value.get("id") or "").strip(),
                version=1, name=str(value.get("name") or "").strip(), status="CANONICAL",
                fields={
                    "identity": {"role": value.get("role"), "family_id": value.get("family_id"), "status": value.get("status", "alive")},
                    "visual_identity": {"description": visual},
                    "visual_bible": {"design": visual, "forbidden_variations": ["face redesign", "body proportion drift", "unapproved wardrobe redesign", "age drift"]},
                    "voice_profile": {"description": voice, "target_locale": "ar-EG"},
                    "speech_style": {"language": "Egyptian Arabic", "original_dialogue_only": True},
                    "canonical_facts": [{"traits": list(value.get("traits") or []), "family_id": value.get("family_id")}],
                    "continuity": ["same character identity across episodes", "same canonical visual reference", "same voice identity unless explicitly versioned"],
                    "assets": [{"asset_id": f"character-ref-{value.get('character_id')}", "type": "canonical_reference", "status": "reference_required"}],
                    "rights": {"status": "CLEARED", "commercial_use": True, "owner": "Kemet original production"},
                },
            ))
        if not output:
            raise ValueError("canonical_characters_required")
        return output

    @staticmethod
    def _scene(scene: Mapping[str, Any], episode_id: str, index: int) -> dict[str, Any]:
        item = dict(scene)
        item["scene_id"] = str(item.get("scene_id") or f"{episode_id}-sc{index}")
        item["sequence"] = index
        item["digest"] = sha256(json.dumps(item, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()).hexdigest()
        item["visual_direction"] = {"style": "canonical Mendes World", "camera": "cinematic", "lighting": "motivated", "text_overlay": False}
        return item

    @staticmethod
    def _shot(scene: Mapping[str, Any]) -> dict[str, Any]:
        characters = list(scene.get("characters") or [])
        return {
            "shot_id": f"{scene['scene_id']}-sh1",
            "action": str(scene.get("description") or ""),
            "emotion": "wonder_then_tension",
            "camera": "establishing" if len(characters) > 1 else "medium_close",
            "lens": "35mm cinematic equivalent",
            "framing": "story-driven composition",
            "movement": "controlled push-in",
            "lighting": "motivated evening light with restrained blue accent",
            "time": "evening",
            "dialogue": str(scene.get("dialogue") or ""),
            "duration_seconds": int(scene.get("duration_seconds") or 1),
            "transition": "cut",
            "reference_asset_ids": [f"character-ref-{x}" for x in characters],
        }

    @staticmethod
    def _reference_assets(episode_id: str, characters: list[Mapping[str, Any]], world: Mapping[str, Any]) -> list[dict[str, Any]]:
        assets = []
        for character in characters:
            assets.append({"asset_id": f"character-ref-{character['character_id']}", "type": "canonical_character_reference", "character_ids": [character["character_id"]], "world_id": world["world_id"], "reference_of": character["character_id"], "sha256": None, "rights_status": "CLEARED"})
        assets.append({"asset_id": "world-ref-mendes-v1", "type": "canonical_world_reference", "character_ids": [], "world_id": world["world_id"], "reference_of": world["world_id"], "sha256": None, "rights_status": "CLEARED"})
        return assets


mendes_cinematic_orchestrator = MendesCinematicOrchestrator()
