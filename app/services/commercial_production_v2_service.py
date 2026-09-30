"""Canonical Commercial Production V2 compiler for Kemet Production OS.

Compiles a provider-independent commercial specification into the existing
cinematic graph, production planning, quality gate, and revenue-path contracts.
It never executes generation, publication, payment, or other external effects.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from app.services.cinematic_production_os import cinematic_production_os
from app.services.cinematic_quality_readiness_gate import cinematic_quality_readiness_gate
from app.services.production_studio_service import production_studio_service
from app.services.production_reference_service import production_reference_service
from app.services.visual_direction_service import visual_direction_service


class CommercialProductionV2Service:
    VERSION = "1.0"
    SCHEMA = "kemet.commercial.production_v2.v1"
    SHOT_COUNT = 7
    SHOTS = (
        ("01", "fragmentation", "Business fragmentation", 6),
        ("02", "command_layer", "Kemet control layer", 7),
        ("03", "intelligence", "ASK -> PLAN -> SIMULATE", 7),
        ("04", "approval", "Human approval", 6),
        ("05", "execution", "Governed execution", 7),
        ("06", "outcome", "Business outcomes", 6),
        ("07", "brand", "Kemet brand close", 6),
    )
    SHOT_DIRECTION = {
        "01": {"camera": "slow controlled dolly through a premium office at blue-hour", "lens": "35mm anamorphic", "motion": "floating screens, overlapping notifications, restrained handheld micro-motion", "lighting": "cool practicals with soft contrast", "narration": "Information everywhere. Decisions everywhere. One business, fragmented.", "on_screen": "No readable generated UI; abstract fragments only.", "transition": "match-motion collapse into a single central point"},
        "02": {"camera": "locked symmetrical push-in toward the Kemet command layer", "lens": "50mm anamorphic", "motion": "fragmented elements align into one coherent spatial system", "lighting": "neutral white with precise luminous accents", "narration": "What if your business could finally work as one?", "on_screen": "Real Kemet UI composited in post: command center, brand typography, verified layout.", "transition": "hard visual alignment on the Kemet command layer"},
        "03": {"camera": "macro-to-wide rack focus across the canonical Kemet flow", "lens": "65mm macro into 40mm", "motion": "ASK becomes PLAN, PLAN becomes SIMULATE with continuous causal movement", "lighting": "clean studio light, high local contrast", "narration": "Ask. Plan. Simulate. See the path before anything happens.", "on_screen": "Post-composited exact labels: ASK -> PLAN -> SIMULATE.", "transition": "data-line wipe into approval state"},
        "04": {"camera": "over-shoulder toward a single human approval moment", "lens": "50mm", "motion": "everything pauses except the approval control and subtle breathing motion", "lighting": "warm human key against controlled neutral environment", "narration": "And when action matters, you stay in control.", "on_screen": "Post-composited approval card with clear human approval state; no fake approval claim.", "transition": "approval confirmation becomes a precise forward pulse"},
        "05": {"camera": "fast but readable tracking move through connected business systems", "lens": "32mm anamorphic", "motion": "one governed action propagates through connected workflows", "lighting": "neutral premium contrast with controlled highlights", "narration": "Then Kemet turns intent into governed execution.", "on_screen": "Post-composited execution trace, evidence, and canonical lifecycle indicators.", "transition": "execution trace resolves into measurable outcomes"},
        "06": {"camera": "wide reveal from operational detail to calm executive view", "lens": "40mm", "motion": "chaos is replaced by stable, legible business flow", "lighting": "bright premium daylight with soft depth", "narration": "Less fragmentation. Clearer decisions. Measurable business outcomes.", "on_screen": "Post-composited verified outcome placeholders; never invent metrics.", "transition": "slow fade toward brand mark"},
        "07": {"camera": "minimal centered hero frame with subtle forward drift", "lens": "75mm", "motion": "almost still; only a refined light sweep", "lighting": "clean white studio with premium depth", "narration": "Kemet AI BOS. Don't use another AI tool. Run your business with Kemet.", "on_screen": "Exact Kemet logo, typography, and CTA composited in post.", "transition": "clean end card hold for two seconds"},
    }

    def build(self, *, organization_id: int, project_id: str = "kemet-commercial-v2",
               title: str = "The Control Layer", language: str = "en",
               platforms: list[str] | None = None) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            raise ValueError("organization_required")
        if language not in {"en", "ar-EG", "ar"}:
            raise ValueError("unsupported_language")
        selected = [str(x).strip().lower() for x in (platforms or ["youtube", "telegram"])]
        if not selected or any(not x for x in selected):
            raise ValueError("platforms_required")

        state = cinematic_production_os.build_state(
            organization_id=org,
            project_id=project_id,
            stage="PLANNED",
            intent={"title": title, "duration_seconds": 45, "format": "16:9"},
            visual_direction={
                "style": "premium enterprise technology film",
                "realistic": True,
                "minimal": True,
                "ui_text_post_composited": True,
                "id": "cinematic",
            },
        )
        production_profile = visual_direction_service.compile_profile(
            "cinematic", task_type="commercial"
        )
        shots = [
            {
                "shot_id": sid,
                "purpose": purpose,
                "description": description,
                "duration_seconds": duration,
                "visual_rule": "generated imagery carries scene mood; exact Kemet UI and typography are composited in post",
                "audio_rule": "clean dialogue/voice, designed sound, controlled music bed, objective A/V sync check",
                "continuity_rule": "bind character/world/style references before generation",
                **self.SHOT_DIRECTION[sid],
            }
            for sid, purpose, description, duration in self.SHOTS
        ]
        golden_reference = production_reference_service.build_pack(
            organization_id=org, project_id=project_id,
            visual_direction={"id": "cinematic", "style": "premium enterprise technology film"},
            characters=[], worlds=[], assets=[], production_profile=production_profile,
        )
        scenes = [{"scene_id": f"scene-{i}", "shot_id": shot["shot_id"]} for i, shot in enumerate(shots, 1)]
        planning_projection = cinematic_production_os.compile_planning_projection(
            state=state, golden_reference=golden_reference, shots=shots, scenes=scenes,
            production_profile=production_profile,
        )
        graph = planning_projection["graph"]
        studio = production_studio_service.plan(
            organization_id=org, title=title, language="ar-EG" if language == "ar" else language,
            duration_seconds=45, platforms=selected,
        )
        revenue_path = [
            "content", "distribution", "audience_leads", "offer",
            "payment", "fulfillment", "profit", "measurement", "learning",
        ]
        readiness_evidence = {
            key: {"verified": False, "reason": "real_artifact_or_evidence_required"}
            for key in cinematic_quality_readiness_gate.REQUIRED
        }
        readiness = cinematic_quality_readiness_gate.evaluate(
            organization_id=org, project_id=project_id, evidence=readiness_evidence,
            production_profile=production_profile,
        )
        payload = {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "organization_id": org,
            "project_id": project_id,
            "title": title,
            "creative": {
                "core_idea": "FRAGMENTATION -> CONTROL -> INTELLIGENCE -> APPROVAL -> EXECUTION -> OUTCOME",
                "hook": "What if your business could finally work as one?",
                "positioning": "Kemet is the control layer, not another app, chatbot, or dashboard.",
                "duration_seconds": 45,
                "shots": shots,
            },
            "production_graph": graph,
            "planning_projection": planning_projection,
            "production_specification": planning_projection["specification"],
            "production_profile": production_profile,
            "production_studio": studio,
            "quality_readiness": readiness,
            "revenue_path": {"lifecycle": revenue_path, "commercial_goal": "first_verified_revenue"},
            "governance": {
                "canonical_lifecycle": "ASK -> PLAN -> SIMULATE -> APPROVE -> EXECUTE -> REVIEW -> REPLAY",
                "human_approval_required": True,
                "external_execution": False,
                "execution_authority": False,
                "auto_publish": False,
                "auto_payment": False,
                "mcp": False,
                "provider_independent": True,
            },
            "truth_boundary": {
                "plan_verified": True,
                "artifact_verified": False,
                "publication_verified": False,
                "revenue_verified": False,
                "reason": "planning_compilation is not production or commercial evidence",
            },
        }
        payload["digest"] = sha256(json.dumps(
            payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str
        ).encode()).hexdigest()
        return payload


commercial_production_v2_service = CommercialProductionV2Service()
