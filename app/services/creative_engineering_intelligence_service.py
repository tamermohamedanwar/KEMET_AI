from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CreativeEngineeringSource:
    source_id: str
    name: str
    url: str
    source_type: str
    license: str
    engines: tuple[str, ...]
    transferable_capabilities: tuple[str, ...]
    use_cases: tuple[str, ...]
    integration_mode: str
    execution_authority: bool = False


class CreativeEngineeringIntelligenceService:
    VERSION = "1.0"
    SCHEMA = "kemet.creative_engineering_intelligence.v1"

    SOURCES = (
        CreativeEngineeringSource(
            "oss-games-index", "Awesome Open Source Games",
            "https://github.com/michelpereira/awesome-open-source-games",
            "catalog", "CC0", (),
            ("game_architecture", "genre_patterns", "codebase_reuse", "prototype_discovery"),
            ("games", "content", "creative_prototyping", "engineering_research"),
            "reference_only",
        ),
        CreativeEngineeringSource(
            "gamedev-agent-skills", "Awesome GameDev Agent Skills",
            "https://github.com/gamedev-skills/awesome-gamedev-agent-skills",
            "agent_skill_catalog", "Apache-2.0",
            ("Godot", "Unity", "Unreal", "Phaser", "PixiJS", "three.js", "Bevy", "pygame", "LÖVE", "Roblox"),
            ("game_ai", "procedural_generation", "dialogue", "save_systems", "audio", "shaders", "physics", "level_design", "input_systems", "qa"),
            ("games", "video", "story_worlds", "interactive_content", "engineering"),
            "skill_harvest",
        ),
        CreativeEngineeringSource(
            "godot", "Godot Engine", "https://github.com/godotengine/godot",
            "engine", "MIT", ("Godot",),
            ("scene_graph", "2d", "3d", "animation", "physics", "ui", "cross_platform_export"),
            ("games", "interactive_storytelling", "visual_prototypes", "simulations"),
            "optional_external_toolchain",
        ),
    )

    TRANSFER_MAP = {
        "game_ai": ("decision_support", "simulation", "agent_behavior", "evaluation"),
        "procedural_generation": ("content_variants", "story_variants", "campaign_generation", "synthetic_scenarios"),
        "dialogue": ("script_generation", "character_dialogue", "conversation_design", "voice_content"),
        "save_systems": ("state_persistence", "workflow_resume", "checkpointing", "replay"),
        "audio": ("voice_pipeline", "sound_design", "media_postproduction"),
        "level_design": ("journey_design", "content_structure", "campaign_design", "customer_flows"),
        "qa": ("content_qa", "visual_qa", "regression_testing", "evidence_generation"),
        "physics": ("simulation", "scenario_modeling", "constraint_testing"),
        "ui": ("command_center", "creative_tools", "interactive_content"),
    }

    @classmethod
    def catalog(cls) -> list[dict[str, Any]]:
        return [cls._serialize(source) for source in cls.SOURCES]

    @classmethod
    def _serialize(cls, source: CreativeEngineeringSource) -> dict[str, Any]:
        return {
            "source_id": source.source_id,
            "name": source.name,
            "url": source.url,
            "source_type": source.source_type,
            "license": source.license,
            "engines": list(source.engines),
            "transferable_capabilities": list(source.transferable_capabilities),
            "use_cases": list(source.use_cases),
            "integration_mode": source.integration_mode,
            "execution_authority": False,
        }

    @classmethod
    def transfer(cls, capability: str) -> dict[str, Any]:
        key = str(capability or "").strip().lower()
        return {
            "capability": key,
            "mapped_kemet_domains": list(cls.TRANSFER_MAP.get(key, ())),
            "known": key in cls.TRANSFER_MAP,
            "advisory": True,
            "execution_authority": False,
            "human_approval_required": True,
        }

    @classmethod
    def plan_harvest(cls, requested_domains: list[str] | tuple[str, ...]) -> dict[str, Any]:
        requested = {str(item).strip().lower() for item in requested_domains or () if str(item).strip()}
        selected: list[dict[str, Any]] = []
        for source in cls.SOURCES:
            overlap = sorted(requested.intersection(set(source.transferable_capabilities)))
            if overlap:
                selected.append({
                    "source_id": source.source_id,
                    "capabilities": overlap,
                    "integration_mode": source.integration_mode,
                    "execution_authority": False,
                })
        return {
            "schema": cls.SCHEMA,
            "version": cls.VERSION,
            "requested_domains": sorted(requested),
            "selected_sources": selected,
            "security_review_required": True,
            "license_review_required": True,
            "human_approval_required": True,
            "external_execution": False,
            "canonical_executor": "kemet",
        }


creative_engineering_intelligence_service = CreativeEngineeringIntelligenceService()
