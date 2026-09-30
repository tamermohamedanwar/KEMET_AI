from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any

from app.services.local_media_provider_service import local_media_provider_service
from app.services.tool_intelligence_registry import tool_intelligence_registry


@dataclass(frozen=True)
class ProductionStage:
    stage: str
    capability: str
    quality_gate: str


class ProductionStudioService:
    VERSION = "1.1"
    STAGES = (
        ProductionStage("research", "research", "source_trace"),
        ProductionStage("script", "text_generation", "originality"),
        ProductionStage("visuals", "image_generation", "character_consistency"),
        ProductionStage("motion", "video_generation", "continuity"),
        ProductionStage("voice", "voice_generation", "voice_rights"),
        ProductionStage("edit", "video_generation", "delivery_quality"),
        ProductionStage("review", "research", "policy_and_rights"),
        ProductionStage("distribution", "analytics", "platform_readiness"),
    )

    def plan(self, *, organization_id: int, title: str, language: str = "ar-EG",
             duration_seconds: int = 90, platforms: list[str] | None = None,
             reference_uri: str | None = None) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        if not str(title or "").strip():
            raise ValueError("title_required")
        if duration_seconds < 15 or duration_seconds > 1800:
            raise ValueError("duration_out_of_range")
        if language not in {"ar-EG", "ar", "en"}:
            raise ValueError("unsupported_language")
        platform_list = [str(x).strip().lower() for x in (platforms or ["youtube", "tiktok", "instagram"])]
        stages = []
        for item in self.STAGES:
            recommendations = tool_intelligence_registry.recommend(
                item.capability, organization_id=int(organization_id)
            )
            stage = {
                "stage": item.stage,
                "capability": item.capability,
                "quality_gate": item.quality_gate,
                "tool_recommendations": recommendations,
            }
            if item.stage == "voice":
                stage["local_media_providers"] = local_media_provider_service.snapshot(int(organization_id))["providers"]
                stage["voice_policy"] = {
                    "natural_delivery_preferred": True,
                    "voice_clone_requires_rights_attestation": True,
                    "provider_is_untrusted": True,
                    "execution_authority": False,
                }
            stages.append(stage)
        payload = {
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "title": str(title).strip()[:200],
            "language": language,
            "duration_seconds": int(duration_seconds),
            "platforms": platform_list,
            "reference": {"provided": bool(reference_uri), "uri": reference_uri if reference_uri else None},
            "stages": stages,
            "approval_gates": ["creative", "rights", "budget", "distribution"],
            "budget": {"mode": "estimate_before_execution", "hard_cap": None, "currency": "USD"},
            "execution": {"automatic": False, "canonical_runtime_only": True},
            "governance": {"read_only": True, "human_approval_required": True,
                           "external_execution": False, "database_mutation": False},
        }
        digest_input = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        payload["plan_digest"] = sha256(digest_input.encode("utf-8")).hexdigest()
        return payload


production_studio_service = ProductionStudioService()
