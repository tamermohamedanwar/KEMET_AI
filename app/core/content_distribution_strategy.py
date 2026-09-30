"""Canonical zero-infrastructure-first content distribution strategy."""
from __future__ import annotations
from typing import Any

STRATEGY_VERSION = "1.0"
PRIMARY_CHANNEL = "telegram"
SECONDARY_CHANNELS = ("youtube", "tiktok", "instagram", "facebook")
WEBSITE_STATE = "deferred_until_revenue_evidence"

PRODUCTION_PROFILES = {
    "mobile_now": {
        "target_max_duration_seconds": 300,
        "preferred_duration_seconds": 180,
        "generation_strategy": "short_shots_assembled_into_episode",
        "quality_class": "production_candidate_after_qa",
        "hardware_policy": "phone_or_low_resource_host",
    },
    "workstation_after_revenue": {
        "target_max_duration_seconds": 3600,
        "preferred_duration_seconds": 1800,
        "generation_strategy": "long_form_shot_batches_and_higher_resolution",
        "quality_class": "cinematic_production",
        "hardware_policy": "dedicated_gpu_workstation",
    },
}


def strategy_snapshot() -> dict[str, Any]:
    return {
        "version": STRATEGY_VERSION,
        "primary_distribution": PRIMARY_CHANNEL,
        "secondary_distribution": list(SECONDARY_CHANNELS),
        "website": {
            "state": WEBSITE_STATE,
            "domain_required": False,
            "hosting_required": False,
            "render_required": False,
            "payment_gateway_required": False,
            "activation_rule": "verified_revenue_evidence_covers_recurring_infrastructure_costs",
        },
        "production_principle": "mobile_first_zero_infrastructure_before_revenue",
        "production_profiles": PRODUCTION_PROFILES,
        "current_profile": "mobile_now",
        "approval_required": True,
        "canonical_runtime_only": True,
        "execution_authority": False,
        "external_execution": False,
        "mcp": False,
    }
