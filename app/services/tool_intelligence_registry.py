from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolCapability:
    capability_id: str
    category: str
    description: str


@dataclass(frozen=True)
class ToolCandidate:
    tool_id: str
    name: str
    provider_id: str
    capabilities: tuple[str, ...]
    cost_model: str
    security_tier: str
    provenance: str
    fallback_ids: tuple[str, ...] = ()


class ToolIntelligenceRegistry:
    VERSION = "1.4"
    CAPABILITIES = (
        ToolCapability("text_generation", "content", "Generate and transform text."),
        ToolCapability("image_generation", "media", "Generate visual assets."),
        ToolCapability("video_generation", "media", "Generate or transform video."),
        ToolCapability("voice_generation", "media", "Generate speech or voice."),
        ToolCapability("analytics", "measurement", "Measure audience or business outcomes."),
        ToolCapability("search_visibility", "growth", "Measure search visibility."),
        ToolCapability("research", "intelligence", "Retrieve or synthesize research."),
        ToolCapability("coding", "engineering", "Assist software engineering."),
        ToolCapability("binary_analysis", "security", "Inspect binaries and authorized software artifacts."),
        ToolCapability("validated_application_security_testing", "security", "Validate authorized application security findings with controlled testing evidence."),
        ToolCapability("local_ai_acceleration", "infrastructure", "Probe local AI acceleration availability without granting execution authority."),
        ToolCapability("ml_evaluation", "intelligence", "Evaluate ML models for generalization and evidence quality without deployment authority."),
    )
    TOOLS = (
        ToolCandidate("youtube_analytics", "YouTube Analytics API", "google", ("analytics",), "usage_dependent", "high", "official_google", ("youtube_data",)),
        ToolCandidate("youtube_data", "YouTube Data API", "google", ("analytics",), "quota_dependent", "high", "official_google"),
        ToolCandidate("search_console", "Google Search Console", "google", ("search_visibility", "analytics"), "quota_dependent", "high", "official_google"),
        ToolCandidate("openrouter", "OpenRouter", "openrouter", ("text_generation", "research", "coding"), "usage_dependent", "medium", "official_provider", ("google", "groq", "anthropic")),
        ToolCandidate("google_models", "Google model APIs", "google", ("text_generation", "image_generation", "research", "coding"), "usage_dependent", "high", "official_google", ("openrouter", "groq")),
        ToolCandidate("voder", "VODER local media engine", "local_media", ("voice_generation",), "local_compute", "medium", "external_local_tool", ("google_models", "openrouter")),
        ToolCandidate("olmocr", "AI2 olmOCR", "document_intelligence", ("research",), "local_or_hosted_compute", "high", "official_ai2", ("openrouter", "google_models")),
        ToolCandidate("ghidra", "Ghidra", "nsa_research_directorate", ("binary_analysis",), "local_compute", "high", "official_nsa_ghidra", ()),
        ToolCandidate("strix", "Strix", "usestrix", ("validated_application_security_testing",), "local_compute_or_hosted", "critical", "official_usestrix", ()),
        ToolCandidate("cuda_probe", "NVIDIA CUDA runtime probe", "nvidia", ("local_ai_acceleration",), "local_compute", "high", "official_nvidia", ()),
        ToolCandidate("kemet_ml_evaluation", "Kemet ML Evaluation", "kemet", ("ml_evaluation",), "internal_compute", "high", "internal_kemet", ()),
    )

    @classmethod
    def snapshot(cls, organization_id: int | None) -> dict[str, Any]:
        return {
            "version": cls.VERSION,
            "organization_id": organization_id,
            "purpose": "task_tool_discovery",
            "capabilities": [c.__dict__ for c in cls.CAPABILITIES],
            "tools": [t.__dict__ for t in cls.TOOLS],
            "governance": {
                "discovery_only": True,
                "no_automatic_connection": True,
                "no_secret_discovery": True,
                "no_execution_authority": True,
                "canonical_runtime_required_for_execution": True,
                "official_provider_preferred": True,
                "external_local_tools_untrusted": True,
            },
        }
    @classmethod
    def recommend(cls, capability_id: str, organization_id: int | None = None) -> dict[str, Any]:
        matches = [t for t in cls.TOOLS if capability_id in t.capabilities]
        ranked = sorted(matches, key=lambda t: (t.security_tier != "high", t.cost_model, t.tool_id))
        return {
            "organization_id": organization_id,
            "capability": capability_id,
            "recommendations": [
                {**t.__dict__, "fallback_ids": list(t.fallback_ids)} for t in ranked
            ],
            "selection_policy": {
                "verified_provenance_required": True,
                "security_trust_before_cost": True,
                "fallback_required_for_critical_paths": True,
            },
        }

    @classmethod
    def evaluate(cls, tool_id: str) -> dict[str, Any]:
        tool = next((t for t in cls.TOOLS if t.tool_id == tool_id), None)
        if tool is None:
            return {"tool_id": tool_id, "status": "unknown", "verified": False}
        return {
            "tool_id": tool.tool_id,
            "provider_id": tool.provider_id,
            "cost_model": tool.cost_model,
            "security_tier": tool.security_tier,
            "provenance": tool.provenance,
            "verified": tool.provenance.startswith("official_") or tool.provenance == "official_provider",
            "outcome_measurement_required": True,
            "execution_authority": "canonical_runtime_only",
        }


tool_intelligence_registry = ToolIntelligenceRegistry()

