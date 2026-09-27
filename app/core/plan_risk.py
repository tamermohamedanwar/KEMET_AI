from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class PlanRiskAssessment:
    level: str
    score: int
    approval_required: bool
    external_side_effects: bool
    database_mutation: bool
    affected_resources: tuple[str, ...]
    reasons: tuple[str, ...]
    assessment_hash: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def assess_plan_risk(plan: Any) -> PlanRiskAssessment:
    score = 0
    reasons: list[str] = []
    resources: set[str] = set()
    external = False
    mutation = False
    for step in plan.steps:
        action = str(step.action).lower()
        resources.add(action)
        if step.risk == "high" or step.requires_approval:
            score += 40
            reasons.append(f"approval:{step.step_id}")
        if action in {"send", "update", "create", "delete", "execute", "publish"}:
            score += 30
            external = True
            reasons.append(f"external:{step.step_id}")
        if action in {"db_write", "update", "create", "delete", "refund", "invoice"}:
            score += 30
            mutation = True
            reasons.append(f"mutation:{step.step_id}")
    score = min(100, score)
    level = "high" if score >= 70 else "medium" if score >= 30 else "low"
    payload = {"level": level, "score": score, "approval_required": score >= 30,
               "external_side_effects": external, "database_mutation": mutation,
               "affected_resources": sorted(resources), "reasons": reasons}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return PlanRiskAssessment(level, score, score >= 30, external, mutation,
                              tuple(sorted(resources)), tuple(reasons), digest)
