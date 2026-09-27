from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApprovalPackage:
    organization_id: int
    plan_hash: str
    context_fingerprint: str
    risk_level: str
    risk_score: int
    approval_required: bool
    external_side_effects: bool
    database_mutation: bool
    affected_resources: tuple[str, ...]
    reasons: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    package_hash: str
    evidence_context_hash: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "plan_hash": self.plan_hash,
            "context_fingerprint": self.context_fingerprint,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "approval_required": self.approval_required,
            "external_side_effects": self.external_side_effects,
            "database_mutation": self.database_mutation,
            "affected_resources": list(self.affected_resources),
            "reasons": list(self.reasons),
            "evidence_requirements": list(self.evidence_requirements),
            "package_hash": self.package_hash,
            "evidence_context_hash": self.evidence_context_hash,
        }


def build_approval_package(
    plan: Any,
    binding: dict[str, Any],
    assessment: Any,
    *,
    evidence_context_hash: str = "",
) -> ApprovalPackage:
    org = int(binding.get("organization_id", 0))
    if org <= 0 or getattr(plan, "organization_id", None) != org:
        raise ValueError("tenant_context_mismatch")
    plan_hash = str(binding.get("plan_hash", ""))
    context = str(binding.get("context_fingerprint", ""))
    if not plan_hash or not context:
        raise ValueError("approval_binding_required")
    evidence = {"decision", "plan", "risk_assessment"}
    if assessment.external_side_effects:
        evidence.add("external_effect")
    if assessment.database_mutation:
        evidence.add("database_mutation")
    payload = {
        "organization_id": org, "plan_hash": plan_hash,
        "context_fingerprint": context, "risk_level": assessment.level,
        "risk_score": assessment.score, "approval_required": assessment.approval_required,
        "external_side_effects": assessment.external_side_effects,
        "database_mutation": assessment.database_mutation,
        "affected_resources": sorted(assessment.affected_resources),
        "reasons": list(assessment.reasons),
        "evidence_requirements": sorted(evidence),
        "evidence_context_hash": str(evidence_context_hash or ""),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return ApprovalPackage(package_hash=digest, **payload)
