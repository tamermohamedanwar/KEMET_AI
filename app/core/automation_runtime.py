from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

from app.automation.action_registry import registry as action_registry
from app.core.automation_control_plane import AutomationPlan, automation_control_plane
from app.core.execution.execution_boundary import execution_boundary
from app.core.execution_checkpoint import execution_checkpoint
from flask import has_app_context


@dataclass
class ExecutionReceipt:
    plan_id: str
    plan_hash: str
    execution_key: str
    status: str
    started_at: float
    finished_at: float | None = None
    executed: bool = False
    steps: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"plan_id": self.plan_id, "plan_hash": self.plan_hash,
                "execution_key": self.execution_key, "status": self.status,
                "started_at": self.started_at, "finished_at": self.finished_at,
                "executed": self.executed, "steps": self.steps, "error": self.error}


class AutomationRuntime:
    """Deterministic governed runtime with execution-scoped idempotency."""

    VERSION = "2.0"
    _completed: set[str] = set()

    def _receipt_id(self, plan_hash: str, execution_key: str = "") -> str:
        return hashlib.sha256(f"{plan_hash}:{execution_key}:receipt".encode()).hexdigest()

    def simulate(self, plan: AutomationPlan) -> dict[str, Any]:
        compiled = automation_control_plane.compile(plan)
        if not compiled["success"]:
            return compiled
        execution_key = f"simulation:{plan.plan_id}"
        return {**compiled, "runtime": self.VERSION, "mode": "simulation",
                "receipt_id": self._receipt_id(compiled["plan_hash"], execution_key),
                "steps": [{"step_id": step.step_id, "action": step.action, "status": "simulated"}
                          for step in plan.steps]}
    def _authorization_for_step(self, authorization: dict[str, Any] | None,
                                step_id: str) -> dict[str, Any] | None:
        if not authorization:
            return None
        authorizations = authorization.get("authorizations")
        if isinstance(authorizations, dict):
            value = authorizations.get(step_id)
            return value if isinstance(value, dict) else None
        return authorization

    def execute(self, plan: AutomationPlan, *, authorization: dict[str, Any] | None = None,
                actor_id: str | None = None, execution_key: str | None = None,
                deadline_at: float | None = None) -> dict[str, Any]:
        compiled = automation_control_plane.compile(plan)
        if not compiled["success"]:
            return compiled
        if plan.dry_run:
            return self.simulate(plan)
        plan_hash = compiled["plan_hash"]
        key = str(execution_key or plan.plan_id or plan_hash)
        if key in self._completed:
            return {**compiled, "status": "idempotent_replay_blocked", "executed": False,
                    "execution_key": key}

        for step in plan.steps:
            if not step.requires_approval:
                continue
            gate = execution_boundary.require(
                plan=compiled["plan"],
                authorization=self._authorization_for_step(authorization, step.step_id),
                action=step.action,
            )
            if not gate.get("allowed"):
                return {**compiled, "status": "blocked", "gate": gate, "executed": False}

        checkpoint_enabled = bool(plan.organization_id and has_app_context())
        receipt = ExecutionReceipt(plan_id=plan.plan_id, plan_hash=plan_hash,
                                   execution_key=key, status="running", started_at=time.time())
        for ordinal, step in enumerate(plan.steps):
            if deadline_at is not None and time.time() >= deadline_at:
                receipt.status = "deadline_exceeded"
                receipt.error = "execution_deadline_exceeded"
                receipt.finished_at = time.time()
                return {**compiled, "status": receipt.status, "receipt": receipt.as_dict(),
                        "executed": receipt.executed}
            if checkpoint_enabled:
                checkpoint = execution_checkpoint.begin_step(
                    organization_id=int(plan.organization_id), execution_key=key,
                    plan_hash=plan_hash, step_id=step.step_id, ordinal=ordinal,
                    worker_id=actor_id,
                )
                if checkpoint["status"] == "completed":
                    receipt.steps.append({"step_id": step.step_id, "action": step.action,
                                          "status": "resumed_from_checkpoint",
                                          "result": checkpoint["checkpoint"]["result"]})
                    continue
                if checkpoint["status"] in {"ambiguous", "plan_hash_mismatch"}:
                    receipt.status = "blocked_ambiguous_checkpoint"
                    receipt.error = "checkpoint_requires_reconciliation"
                    receipt.finished_at = time.time()
                    return {**compiled, "status": receipt.status,
                            "receipt": receipt.as_dict(), "executed": receipt.executed}
            started = time.time()
            try:
                result = action_registry.execute(step.action, parameters=step.parameters, user_id=actor_id)
            except Exception as exc:
                result = {"success": False, "error": "step_execution_exception", "message": str(exc)}
            step_ok = bool(result.get("success"))
            receipt.executed = True
            receipt.steps.append({"step_id": step.step_id, "action": step.action,
                                  "status": "completed" if step_ok else "failed",
                                  "duration_seconds": round(time.time() - started, 6), "result": result})
            if checkpoint_enabled and step_ok:
                execution_checkpoint.complete_step(
                    organization_id=int(plan.organization_id), execution_key=key,
                    plan_hash=plan_hash, step_id=step.step_id, result=result,
                    worker_id=actor_id,
                )
            if not step_ok:
                if checkpoint_enabled:
                    execution_checkpoint.mark_ambiguous(
                        organization_id=int(plan.organization_id), execution_key=key,
                        plan_hash=plan_hash, step_id=step.step_id,
                        reason=str(result.get("error") or "step_failed"), worker_id=actor_id,
                    )
                receipt.status = "failed"
                receipt.error = result.get("error") or result.get("message") or "step_failed"
                receipt.finished_at = time.time()
                return {**compiled, "status": "failed", "receipt": receipt.as_dict(), "executed": True}
        self._completed.add(key)
        receipt.status = "completed"
        receipt.finished_at = time.time()
        return {**compiled, "status": "completed", "receipt": receipt.as_dict(), "executed": True,
                "execution_key": key}


automation_runtime = AutomationRuntime()
