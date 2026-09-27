from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from app.core.automation_control_plane import AutomationLimits, AutomationPlan, AutomationStep
from app.core.task_classifier import TaskClassification, classify_task


@dataclass(frozen=True)
class PlannedStep:
    step_id: str
    objective: str
    action: str
    risk: str
    requires_approval: bool
    depends_on: tuple[str, ...] = ()
    capabilities: frozenset[str] = frozenset()
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TaskPlan:
    task_id: str
    organization_id: int
    task_type: str
    risk: str
    confidence: float
    steps: tuple[PlannedStep, ...]
    requires_approval: bool
    plan_hash: str

    def as_dict(self) -> dict[str, Any]:
        steps = []
        for step in self.steps:
            item = asdict(step)
            item["depends_on"] = list(step.depends_on)
            item["capabilities"] = sorted(step.capabilities)
            steps.append(item)
        return {
            "task_id": self.task_id, "organization_id": self.organization_id,
            "task_type": self.task_type, "risk": self.risk, "confidence": self.confidence,
            "steps": steps,
            "requires_approval": self.requires_approval, "plan_hash": self.plan_hash,
        }


class TaskPlanningEngine:
    VERSION = "1.0"

    def classify(self, prompt: str) -> TaskClassification:
        return classify_task(prompt)

    def plan(self, prompt: str, *, organization_id: int, task_id: str = "task") -> TaskPlan:
        if organization_id <= 0:
            raise ValueError("organization_id_required")
        classification = self.classify(prompt)
        steps = self._decompose(prompt, classification)
        requires_approval = any(step.requires_approval for step in steps)
        payload = {
            "task_id": task_id, "organization_id": organization_id,
            "task_type": classification.task_type, "risk": classification.risk,
            "steps": [asdict(step) for step in steps],
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        return TaskPlan(task_id, organization_id, classification.task_type, classification.risk,
                        classification.confidence, tuple(steps), requires_approval, digest)

    def bind_specialist(self, plan: TaskPlan, *, provider_id: str, action: str) -> TaskPlan:
        if not provider_id or not action:
            raise ValueError("specialist_binding_required")
        if not plan.steps:
            raise ValueError("execution_plan_empty")
        steps = list(plan.steps)
        first = steps[0]
        steps[0] = PlannedStep(first.step_id, first.objective, action, first.risk, True, first.depends_on, first.capabilities, first.parameters)
        payload = {"task_id": plan.task_id, "organization_id": plan.organization_id, "task_type": plan.task_type, "risk": plan.risk, "steps": [asdict(step) for step in steps]}
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        return TaskPlan(plan.task_id, plan.organization_id, plan.task_type, plan.risk, plan.confidence, tuple(steps), True, digest)

    def bind_federated_execution(self, plan: TaskPlan, *, provider_id: str, model_id: str | None = None) -> TaskPlan:
        if not provider_id:
            raise ValueError("federation_provider_required")
        if not plan.steps:
            raise ValueError("execution_plan_empty")
        steps = list(plan.steps)
        if any(step.action == "termux_engineering" for step in steps):
            return plan
        index = next((i for i in range(len(steps) - 1, -1, -1) if steps[i].requires_approval), len(steps) - 1)
        step = steps[index]
        parameters = dict(step.parameters or {})
        parameters.update({"provider_id": provider_id, "model_id": model_id})
        steps[index] = PlannedStep(
            step.step_id, step.objective, "federated_command", "high", True,
            step.depends_on, step.capabilities, parameters,
        )
        payload = {
            "task_id": plan.task_id, "organization_id": plan.organization_id,
            "task_type": plan.task_type, "risk": plan.risk,
            "steps": [asdict(item) for item in steps],
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        return TaskPlan(
            plan.task_id, plan.organization_id, plan.task_type, plan.risk, plan.confidence,
            tuple(steps), True, digest,
        )

    def bind_youtube_publish(self, plan: TaskPlan, *, manifest: str) -> TaskPlan:
        if not str(manifest or '').strip():
            raise ValueError("youtube_manifest_required")
        if not plan.steps:
            raise ValueError("execution_plan_empty")
        steps = list(plan.steps)
        index = next((i for i in range(len(steps) - 1, -1, -1) if steps[i].requires_approval), len(steps) - 1)
        step = steps[index]
        steps[index] = PlannedStep(
            step.step_id,
            "Publish the approved content artifact to YouTube through the governed private-first connector",
            "youtube_publish",
            "high",
            True,
            step.depends_on,
            frozenset(set(step.capabilities) | {"content_publishing", "external_execution"}),
            {"manifest": str(manifest)},
        )
        payload = {
            "task_id": plan.task_id, "organization_id": plan.organization_id,
            "task_type": plan.task_type, "risk": "high",
            "steps": [asdict(item) for item in steps],
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        return TaskPlan(
            plan.task_id, plan.organization_id, plan.task_type, "high", plan.confidence,
            tuple(steps), True, digest,
        )

    def bind_artifact_write(self, plan: TaskPlan, *, artifacts: list[dict[str, Any]], preview_digest: str) -> TaskPlan:
        if not isinstance(artifacts, list) or not artifacts:
            raise ValueError("artifact_binding_required")
        if not preview_digest:
            raise ValueError("artifact_preview_binding_required")
        step = PlannedStep(
            "artifact",
            "Apply the approved artifact set through the governed execution fabric",
            "artifact_write",
            "high",
            True,
            capabilities=frozenset({"coding"}),
            parameters={"artifacts": artifacts, "preview_digest": preview_digest},
        )
        steps = tuple(plan.steps) + (step,)
        payload = {
            "task_id": plan.task_id, "organization_id": plan.organization_id,
            "task_type": plan.task_type, "risk": "high",
            "steps": [asdict(item) for item in steps],
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        return TaskPlan(plan.task_id, plan.organization_id, plan.task_type, "high",
                        plan.confidence, steps, True, digest)

    def compile(self, plan: TaskPlan) -> dict[str, Any]:
        automation_steps = tuple(
            AutomationStep(step_id=s.step_id, action=s.action, parameters=s.parameters,
                            risk=s.risk, requires_approval=s.requires_approval)
            for s in plan.steps
        )
        automation = AutomationPlan(
            plan_id=plan.task_id, organization_id=plan.organization_id,
            trigger=f"task:{plan.task_type}", steps=automation_steps,
            dry_run=True, approval_policy="human" if plan.requires_approval else "auto_safe",
            limits=AutomationLimits(max_steps=max(20, len(automation_steps))),
            metadata={"task_plan_hash": plan.plan_hash, "task_type": plan.task_type},
        )
        return {"task_plan": plan.as_dict(), "automation_plan": automation.canonical(),
                "simulation": True, "executed": False, "approval_required": plan.requires_approval}

    def _decompose(self, prompt: str, classification: TaskClassification) -> list[PlannedStep]:
        steps: list[PlannedStep] = []
        base_risk = "high" if classification.risk == "high" else "low"
        if classification.task_type == "multi_task":
            steps.append(PlannedStep("understand", "Clarify objectives and constraints", "business_insights",
                                     "low", False, capabilities=frozenset({"reasoning"})))
            steps.append(PlannedStep("prepare", "Prepare a governed execution plan", "business_insights",
                                     base_risk, classification.risk == "high", ("understand",), classification.capabilities))
            return steps
        action = "business_insights"
        objective = "Analyze the request and produce a governed plan"
        engineering_operation = self._engineering_operation(prompt)
        if engineering_operation:
            return [PlannedStep(
                "termux",
                f"Run the governed Termux operation: {engineering_operation}",
                "termux_engineering",
                "high",
                True,
                capabilities=frozenset({"coding"}),
                parameters={"operation": engineering_operation},
            )]
        if classification.task_type == "coding":
            objective = "Analyze the software task and prepare implementation work"
        elif classification.task_type == "research":
            objective = "Research and compare the requested subject"
        elif classification.task_type == "multimodal":
            objective = "Analyze the supplied visual or media task"
        elif classification.task_type == "automation":
            objective = "Prepare the requested automation for approval"
            base_risk = "high"
        steps.append(PlannedStep("analyze", objective, action, "low", False,
                                 capabilities=classification.capabilities))
        if classification.task_type in {"coding", "automation"}:
            steps.append(PlannedStep("propose", "Produce the bounded next operation for review", action,
                                     base_risk, True, ("analyze",), classification.capabilities))
        return steps

    @staticmethod
    def _engineering_operation(prompt: str) -> str | None:
        text = str(prompt or "").lower()
        if "git status" in text or "show git" in text or "check changes" in text:
            return "git_status"
        if "compile" in text or "syntax" in text:
            return "compile"
        if "test health" in text:
            return "test_health"
        if "kemet health" in text or "project health" in text:
            return "health"
        return None



task_planner = TaskPlanningEngine()
