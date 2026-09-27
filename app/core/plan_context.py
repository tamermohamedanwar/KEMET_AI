from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PlanContext:
    organization_id: int
    user_id: int | None = None
    allowed_providers: tuple[str, ...] = ()
    allowed_models: tuple[str, ...] = ()
    policy_version: str = "1"
    metadata: dict[str, Any] = field(default_factory=dict)

    def canonical(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "allowed_providers": sorted(self.allowed_providers),
            "allowed_models": sorted(self.allowed_models),
            "policy_version": self.policy_version,
            "metadata": self.metadata,
        }

    def fingerprint(self) -> str:
        payload = json.dumps(self.canonical(), sort_keys=True, default=str).encode()
        return hashlib.sha256(payload).hexdigest()


def bind_plan_context(plan: Any, context: PlanContext) -> dict[str, Any]:
    if context.organization_id <= 0:
        raise ValueError("organization_id_required")
    if getattr(plan, "organization_id", None) != context.organization_id:
        raise ValueError("tenant_context_mismatch")
    return {
        "plan_hash": plan.plan_hash,
        "context_fingerprint": context.fingerprint(),
        "organization_id": context.organization_id,
        "policy_version": context.policy_version,
    }
