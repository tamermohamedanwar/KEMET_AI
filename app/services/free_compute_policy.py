"""Kemet free-first compute policy boundary."""
from __future__ import annotations

from dataclasses import dataclass

SCHEMA = "kemet.media.free_compute_policy.v1"
VERSION = "1.0"


@dataclass(frozen=True)
class FreeComputeDecision:
    provider_id: str
    eligible: bool
    reason: str
    requires_capacity_attestation: bool = True
    execution_authority: bool = False
    external_execution: bool = False
    mcp: bool = False


def evaluate(provider_id: str, *, configured: bool, healthy: bool, available: bool, free_tier: bool, quota_remaining: bool) -> FreeComputeDecision:
    if not free_tier:
        return FreeComputeDecision(provider_id, False, "not_free_tier")
    if not configured:
        return FreeComputeDecision(provider_id, False, "not_configured")
    if not healthy:
        return FreeComputeDecision(provider_id, False, "not_healthy")
    if not available:
        return FreeComputeDecision(provider_id, False, "capacity_unavailable")
    if not quota_remaining:
        return FreeComputeDecision(provider_id, False, "free_quota_exhausted")
    return FreeComputeDecision(provider_id, True, "free_capacity_ready")
