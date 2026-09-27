from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from typing import Any

from app.automation.action_registry import registry as action_registry
from app.core.integration.connector_registry import connector_registry


RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
VALID_RISKS = frozenset(RISK_ORDER)


@dataclass(frozen=True)
class AutomationLimits:
    max_steps: int = 20
    max_retries_per_step: int = 2
    max_runtime_seconds: int = 300
    max_external_operations: int = 10
    max_estimated_cost: float = 100.0

    def validate(self) -> list[str]:
        errors: list[str] = []
        if isinstance(self.max_steps, bool) or not isinstance(self.max_steps, int) or self.max_steps < 1:
            errors.append("max_steps_invalid")
        if isinstance(self.max_retries_per_step, bool) or not isinstance(self.max_retries_per_step, int) or self.max_retries_per_step < 0:
            errors.append("max_retries_invalid")
        if isinstance(self.max_runtime_seconds, bool) or not isinstance(self.max_runtime_seconds, int) or self.max_runtime_seconds < 1:
            errors.append("max_runtime_invalid")
        if isinstance(self.max_external_operations, bool) or not isinstance(self.max_external_operations, int) or self.max_external_operations < 0:
            errors.append("max_external_operations_invalid")
        if isinstance(self.max_estimated_cost, bool) or not isinstance(self.max_estimated_cost, (int, float)) or not math.isfinite(float(self.max_estimated_cost)) or self.max_estimated_cost < 0:
            errors.append("max_estimated_cost_invalid")
        if self.max_steps < 1:
            errors.append("max_steps_invalid")
        return errors


@dataclass(frozen=True)
class AutomationStep:
    step_id: str
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)
    connector_id: str | None = None
    operation: str | None = None
    risk: str = "low"
    requires_approval: bool = False
    reversible: bool = True
    estimated_cost: float = 0.0
    max_retries: int = 0

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AutomationPlan:
    plan_id: str
    organization_id: int
    trigger: str
    steps: tuple[AutomationStep, ...]
    dry_run: bool = True
    approval_policy: str = "auto_safe"
    limits: AutomationLimits = field(default_factory=AutomationLimits)
    metadata: dict[str, Any] = field(default_factory=dict)

    def canonical(self) -> dict[str, Any]:
        payload = {
            "plan_id": self.plan_id,
            "organization_id": self.organization_id,
            "trigger": self.trigger,
            "steps": [step.as_dict() for step in self.steps],
            "dry_run": self.dry_run,
            "approval_policy": self.approval_policy,
            "limits": asdict(self.limits),
            "metadata": self.metadata,
        }
        return payload


class AutomationControlPlane:
    """Plan, validate, and govern automation without performing side effects."""

    VERSION = "1.1"
    DEFAULT_MAX_ESTIMATED_COST_CEILING = 100.0
    VALID_APPROVAL_POLICIES = frozenset({"auto_safe", "human", "human_critical", "blocked"})

    def __init__(self, *, max_estimated_cost_ceiling: float | None = None):
        ceiling = self.DEFAULT_MAX_ESTIMATED_COST_CEILING if max_estimated_cost_ceiling is None else max_estimated_cost_ceiling
        if isinstance(ceiling, bool) or not isinstance(ceiling, (int, float)) or not math.isfinite(float(ceiling)) or ceiling < 0:
            raise ValueError("max_estimated_cost_ceiling_invalid")
        self.max_estimated_cost_ceiling = float(ceiling)

    def _risk(self, step: AutomationStep) -> str:
        return step.risk if step.risk in VALID_RISKS else "critical"

    def _plan_hash(self, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def validate(self, plan: AutomationPlan) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []
        limits_errors = plan.limits.validate()
        errors.extend(limits_errors)
        if plan.limits.max_estimated_cost > self.max_estimated_cost_ceiling:
            errors.append("estimated_cost_ceiling_exceeded")

        if plan.organization_id <= 0:
            errors.append("organization_id_required")
        if not str(plan.trigger).strip():
            errors.append("trigger_required")
        if plan.approval_policy not in self.VALID_APPROVAL_POLICIES:
            errors.append("invalid_approval_policy")
        if len(plan.steps) == 0:
            errors.append("steps_required")
        if len(plan.steps) > plan.limits.max_steps:
            errors.append("step_budget_exceeded")

        external_count = 0
        estimated_cost = 0.0
        max_risk = "low"
        seen_ids: set[str] = set()

        for index, step in enumerate(plan.steps, start=1):
            if not step.step_id.strip() or step.step_id in seen_ids:
                errors.append("step_id_invalid_or_duplicate")
            seen_ids.add(step.step_id)

            if not step.action.strip():
                errors.append(f"step_{index}_action_required")
            elif not action_registry.exists(step.action):
                errors.append(f"unknown_action:{step.action}")

            risk = self._risk(step)
            if step.risk not in VALID_RISKS:
                errors.append(f"invalid_risk:{step.step_id}")
            if RISK_ORDER[risk] > RISK_ORDER[max_risk]:
                max_risk = risk

            if step.max_retries > plan.limits.max_retries_per_step:
                errors.append(f"retry_budget_exceeded:{step.step_id}")
            if step.max_retries < 0:
                errors.append(f"invalid_retry:{step.step_id}")
            if (
                isinstance(step.estimated_cost, bool)
                or not isinstance(step.estimated_cost, (int, float))
                or not math.isfinite(float(step.estimated_cost))
                or step.estimated_cost < 0
            ):
                errors.append(f"invalid_cost:{step.step_id}")
            else:
                estimated_cost += float(step.estimated_cost)
                if not math.isfinite(estimated_cost):
                    errors.append("estimated_cost_overflow")

            if step.connector_id or step.operation:
                external_count += 1
                if not step.connector_id or not step.operation:
                    errors.append(f"connector_operation_required:{step.step_id}")
                elif not connector_registry.allows(
                    step.connector_id, step.operation, plan.organization_id
                ):
                    errors.append(f"connector_not_allowed:{step.connector_id}:{step.operation}")

            if risk in {"high", "critical"} and not step.requires_approval:
                errors.append(f"human_approval_required:{step.step_id}")
            if risk == "critical" and step.reversible:
                warnings.append(f"critical_step_marked_reversible:{step.step_id}")

        if external_count > plan.limits.max_external_operations:
            errors.append("external_operation_budget_exceeded")
        if estimated_cost > plan.limits.max_estimated_cost:
            errors.append("estimated_cost_budget_exceeded")

        if max_risk == "critical" and plan.approval_policy not in {"human_critical", "blocked"}:
            errors.append("critical_plan_requires_human_critical_policy")
        elif max_risk == "high" and plan.approval_policy == "auto_safe":
            errors.append("high_risk_plan_cannot_use_auto_safe")

        if plan.dry_run:
            warnings.append("dry_run_only_no_side_effects")

        return {
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "risk": max_risk,
            "budgets": {
                "steps": len(plan.steps),
                "external_operations": external_count,
                "estimated_cost": estimated_cost,
                "limits": asdict(plan.limits),
            },
        }

    def compile(self, plan: AutomationPlan) -> dict[str, Any]:
        validation = self.validate(plan)
        payload = plan.canonical()
        plan_hash = self._plan_hash(payload)
        status = "ready" if validation["valid"] else "blocked"
        if validation["valid"] and plan.dry_run:
            status = "simulation_ready"
        return {
            "success": validation["valid"],
            "status": status,
            "control_plane": self.VERSION,
            "plan": payload,
            "plan_hash": plan_hash,
            "validation": validation,
            "execution": {
                "executed": False,
                "external_execution": False,
                "database_mutation": False,
                "approval_required": any(step.requires_approval for step in plan.steps),
            },
        }


automation_control_plane = AutomationControlPlane()
