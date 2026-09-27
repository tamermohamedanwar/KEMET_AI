from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Optional

from app.core.orchestration.command_center_wiring import KemetCommandCenterWiring
from app.core.task_classifier import TaskClassification
from app.core.task_planner import TaskPlan, TaskPlanningEngine, task_planner
from app.core.execution.runtime import canonical_execution_runtime
from app.core.automation_queue import automation_queue
from app.core.automation_outcome_service import automation_outcome_service
from app.core.evidence import execution_evidence_fabric
from app.automation.action_registry import registry as automation_registry
from app.core.agent_reasoning import AgentDecision, KemetModelReasoner
from app.core.agent_tool_registry import kemet_agent_tool_registry
from app.core.application_telemetry import application_telemetry


class AgentRuntimeState:
    ASK = "ask"
    PLAN = "plan"
    SIMULATE = "simulate"
    REASON = "reason"
    GUARD = "guard"
    APPROVE = "approve"
    EXECUTE = "execute"
    VERIFY = "verify"
    EVIDENCE = "evidence"
    OUTCOME = "outcome"
    LEARN = "learn"
    NEXT_ACTION = "next_action"
    REVIEW = "review"
    REPLAY = "replay"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class AgentRun:
    run_id: str
    organization_id: int
    user_id: Any
    instruction: str
    state: str
    classification: dict[str, Any]
    plan: dict[str, Any]
    simulation: dict[str, Any]
    execution: dict[str, Any] | None
    decision: dict[str, Any] | None
    evidence: tuple[dict[str, Any], ...]
    outcome: dict[str, Any] | None
    learning: dict[str, Any] | None
    next_action: str
    evidence_context_hash: str


class KemetAgentRuntime:
    """Single governed Commander loop above Kemet's existing control plane."""

    VERSION = "1.1"

    def __init__(
        self,
        *,
        planner: TaskPlanningEngine | None = None,
        command_center: KemetCommandCenterWiring | None = None,
        reasoner: KemetModelReasoner | None = None,
    ):
        self.planner = planner or task_planner
        self.command_center = command_center or KemetCommandCenterWiring()
        self.reasoner = reasoner or KemetModelReasoner()

    def ask(
        self,
        instruction: str,
        *,
        organization_id: int,
        user_id: Any = None,
        context: Optional[dict[str, Any]] = None,
    ) -> AgentRun:
        if organization_id <= 0:
            raise ValueError("organization_id_required")
        instruction = str(instruction or "").strip()
        if not instruction:
            raise ValueError("instruction_required")

        classification = self.planner.classify(instruction)
        plan = self.planner.plan(
            instruction,
            organization_id=organization_id,
            task_id=self._run_id(instruction, organization_id),
        )
        live = self.command_center.build_command_context(
            organization_id=organization_id,
            user_id=user_id,
            message=instruction,
        )
        merged_context = {**live, **(context or {})}
        simulation = self.planner.compile(plan)
        evidence_context_hash = self._digest(
            {"context": merged_context, "plan_hash": plan.plan_hash}
        )
        plan_dict = plan.as_dict()
        plan_dict["context"] = merged_context
        plan_dict["context_fingerprint"] = evidence_context_hash
        plan_dict["runtime"] = "kemet_agent_runtime"
        plan_dict["runtime_version"] = self.VERSION

        requires_approval = bool(plan.requires_approval)
        state = AgentRuntimeState.APPROVE if requires_approval else AgentRuntimeState.REVIEW
        next_action = "request_human_approval" if requires_approval else "review_result"

        self._trace(run_id=plan.task_id, stage="ask", organization_id=organization_id, state=state, fields={"requires_approval": requires_approval})
        return AgentRun(
            run_id=plan.task_id,
            organization_id=organization_id,
            user_id=user_id,
            instruction=instruction,
            state=state,
            classification=self._classification_dict(classification),
            plan=plan_dict,
            simulation=simulation,
            execution=None,
            decision=None,
            evidence=(),
            outcome=None,
            learning=None,
            next_action=next_action,
            evidence_context_hash=evidence_context_hash,
        )

    def reason(self, run: AgentRun) -> tuple[AgentRun, AgentDecision]:
        if run.organization_id <= 0:
            raise ValueError("organization_id_required")
        specialists = self._specialists()
        decision = self.reasoner.decide(
            run.instruction,
            context=run.plan.get("context") or {},
            specialists=specialists,
            tools=kemet_agent_tool_registry.manifests(),
            organization_id=run.organization_id,
        )
        guarded = self._guard_decision(decision)
        self._trace(run_id=run.run_id, stage="reason", organization_id=run.organization_id, state=AgentRuntimeState.REASON, fields={"specialist": guarded.specialist, "tool": guarded.tool, "confidence": guarded.confidence})
        updated = self._replace(
            run,
            state=AgentRuntimeState.APPROVE if run.state == AgentRuntimeState.APPROVE else AgentRuntimeState.REVIEW,
            decision=guarded.as_dict(),
            next_action=run.next_action,
        )
        return updated, guarded

    def enqueue_long_running(
        self,
        run,
        *,
        authorization,
        actor_id=None,
    ):
        """
        Durable long-running execution path.

        The queue/worker owns lifecycle and recovery.
        CanonicalExecutionRuntime remains the final execution boundary.
        """

        if run is None:
            raise ValueError("agent_run_required")

        if run.state != AgentRuntimeState.APPROVE:
            raise ValueError("agent_run_not_awaiting_approval")

        if not isinstance(authorization, dict) or not authorization:
            raise ValueError("execution_authorization_required")

        plan = dict(run.plan or {})
        organization_id = int(run.organization_id)

        execution_key = str(
            authorization.get("execution_key")
            or plan.get("execution_key")
            or run.run_id
        )

        job_key = execution_key

        queue_payload = {
            "organization_id": organization_id,
            "job_key": job_key,
            "workflow_id": str(
                plan.get("workflow_id")
                or f"agent:{run.run_id}"
            ),
            "execution_id": execution_key,
            "idempotency_key": execution_key,
            "workflow_state": "approved",
            "execution_key": execution_key,
            "plan_hash": str(plan.get("plan_hash") or ""),
            "decision_hash": str(
                plan.get("decision_hash")
                or ""
            ),
            "approval_id": authorization.get("approval_id"),
            "payload": {
                "agent_run_id": run.run_id,
                "instruction": run.instruction,
                "organization_id": organization_id,
                "execution_plan": plan,
                "authorization": authorization,
                "actor_id": actor_id,
                "runtime": "kemet_agent_runtime",
                "runtime_version": self.VERSION,
                "canonical_execution_runtime": True,
                "external_execution_authority": False,
            },
        }

        queued = automation_queue.enqueue(queue_payload)

        return self._replace(
            run,
            state=AgentRuntimeState.EXECUTE,
            execution={
                "status": "queued",
                "execution_status": "queued",
                "executed": False,
                "runtime": "canonical",
                "execution_key": execution_key,
                "job_id": queued.get("job_id"),
                "durable": True,
                "queue": "automation_queue",
                "workflow": "unified_workflow_runtime",
                "checkpoint": "execution_checkpoint",
                "resume_policy": "last_verified_checkpoint",
            },
            next_action="worker_claim_and_execute",
        )

    def execute_approved(
        self,
        run: AgentRun,
        *,
        authorization: dict[str, Any],
    ) -> AgentRun:
        if not isinstance(authorization, dict):
            raise ValueError("execution_authorization_required")
        if run.state != AgentRuntimeState.APPROVE:
            raise ValueError("agent_run_not_awaiting_approval")

        steps = run.plan.get("steps") or []
        if not steps:
            raise ValueError("execution_plan_empty")

        step = steps[0]
        action = str(step.get("action") or "").strip()
        parameters = dict(step.get("parameters") or {})
        parameters.setdefault("organization_id", run.organization_id)
        parameters.setdefault("instruction", run.instruction)

        execution_plan = {
            "plan_id": run.run_id,
            "job_id": run.run_id,
            "organization_id": run.organization_id,
            "action": action,
            "parameters": parameters,
            "plan_hash": run.plan.get("plan_hash"),
            "context": run.plan.get("context"),
            "context_fingerprint": run.evidence_context_hash,
            "runtime": "kemet_agent_runtime",
            "runtime_version": self.VERSION,
        }

        self._trace(run_id=run.run_id, stage="approve", organization_id=run.organization_id, state=AgentRuntimeState.APPROVE, fields={"action": action})
        result = canonical_execution_runtime.execute(
            plan=execution_plan,
            authorization=authorization,
            action_registry=automation_registry,
            user_id=run.user_id,
        )

        evidence_record = execution_evidence_fabric.execution_record(
            action=action,
            plan_hash=run.plan.get("plan_hash"),
            risk=run.classification,
            result=result,
        )
        evidence = tuple([*run.evidence, evidence_record])
        verification = self._verify_execution(run, result, evidence_record)
        outcome = {
            "status": result.get("status", "unknown"),
            "success": bool(result.get("success")),
            "executed": bool(result.get("executed")),
            "objective_match": verification["objective_match"],
            "authoritative": verification["authoritative"],
        }

        if result.get("success"):
            learning = {
                "mode": "observational",
                "execution_status": result.get("status"),
                "objective_match": verification["objective_match"],
                "evidence_quality": verification["evidence_quality"],
                "causal_claim": False,
                "next_action": "measure_real_outcome",
            }
            return self._replace(
                run,
                state=AgentRuntimeState.NEXT_ACTION,
                execution=result,
                evidence=evidence,
                outcome=outcome,
                learning=learning,
                next_action="measure_real_outcome" if not verification["objective_match"] else "review_and_measure",
            )

        learning = {
            "mode": "failure_learning",
            "execution_status": result.get("status"),
            "error": result.get("error"),
            "causal_claim": False,
            "next_action": "investigate_and_replan",
        }
        return self._replace(
            run,
            state=AgentRuntimeState.BLOCKED,
            execution=result,
            evidence=evidence,
            outcome=outcome,
            learning=learning,
            next_action="investigate_and_replan",
        )

    def verify(self, run: AgentRun) -> AgentRun:
        if not run.execution:
            raise ValueError("agent_execution_missing")
        evidence = list(run.evidence)
        latest = evidence[-1] if evidence else {}
        verification = self._verify_execution(run, run.execution, latest)
        outcome = {
            **(run.outcome or {}),
            "objective_match": verification["objective_match"],
            "authoritative": verification["authoritative"],
            "evidence_quality": verification["evidence_quality"],
        }
        return self._replace(
            run,
            state=AgentRuntimeState.EVIDENCE if verification["authoritative"] else AgentRuntimeState.VERIFY,
            outcome=outcome,
            next_action="record_learning" if verification["authoritative"] else "obtain_authoritative_evidence",
        )

    def replay(self, run: AgentRun) -> AgentRun:
        return self._replace(
            run,
            state=AgentRuntimeState.REPLAY,
            next_action="fresh_authorization_required",
        )

    def status(self) -> dict[str, Any]:
        return {
            "ok": True,
            "engine": "kemet_agent_runtime",
            "version": self.VERSION,
            "lifecycle": [
                AgentRuntimeState.ASK,
                AgentRuntimeState.PLAN,
                AgentRuntimeState.SIMULATE,
                AgentRuntimeState.REASON,
                AgentRuntimeState.GUARD,
                AgentRuntimeState.APPROVE,
                AgentRuntimeState.EXECUTE,
                AgentRuntimeState.VERIFY,
                AgentRuntimeState.EVIDENCE,
                AgentRuntimeState.OUTCOME,
                AgentRuntimeState.LEARN,
                AgentRuntimeState.NEXT_ACTION,
                AgentRuntimeState.REPLAY,
            ],
            "canonical_execution_runtime": True,
            "approval_required_for_side_effects": True,
            "one_time_authorization": True,
            "external_execution_authority": False,
            "parallel_executor": False,
            "mcp": False,
            "tracing": True,
            "trace_name": "kemet.agent.run",
        }

    @staticmethod
    def _trace(*, run_id: str, stage: str, organization_id: int, state: str, fields: dict[str, Any] | None = None) -> None:
        span = application_telemetry.tracer.start_span("kemet.agent.run")
        span.set_attribute("kemet.agent.run_id", str(run_id))
        span.set_attribute("kemet.agent.stage", str(stage))
        span.set_attribute("kemet.agent.state", str(state))
        span.set_attribute("kemet.organization_id", int(organization_id))
        for key, value in (fields or {}).items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in {"authorization", "token", "secret", "api_key", "access_token"}:
                value = "[REDACTED]"
            if isinstance(value, (str, int, float, bool)):
                span.set_attribute(f"kemet.agent.{normalized}", value)
        span.end()

    @staticmethod
    def _specialists() -> list[dict[str, Any]]:
        return [
            {"id": "business", "description": "Business goals, customers, KPI, revenue and cost.", "capabilities": ["business", "analytics", "reasoning"]},
            {"id": "intelligence", "description": "Knowledge, evidence and business data.", "capabilities": ["knowledge", "research", "evidence"]},
            {"id": "content", "description": "Content strategy, audience, offers and creative direction.", "capabilities": ["content", "creation", "business"]},
            {"id": "production", "description": "Production, media, assets and quality.", "capabilities": ["production", "multimedia", "quality"]},
            {"id": "distribution", "description": "Distribution and publication planning with evidence.", "capabilities": ["distribution", "publishing", "evidence"]},
            {"id": "revenue", "description": "Leads, sales, payment, fulfillment, revenue and profit.", "capabilities": ["revenue", "sales", "business"]},
            {"id": "learning", "description": "Outcome review, evidence quality and next-action learning.", "capabilities": ["outcome", "learning", "analytics"]},
        ]

    @staticmethod
    def _guard_decision(decision: AgentDecision) -> AgentDecision:
        tool = kemet_agent_tool_registry.get(decision.tool)
        if tool is None:
            raise ValueError("agent_guard_unknown_tool")
        if decision.confidence < 0.0 or decision.confidence > 1.0:
            raise ValueError("agent_guard_invalid_confidence")
        return decision

    @staticmethod
    def _verify_execution(run: AgentRun, result: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
        executed = bool(result.get("executed"))
        success = bool(result.get("success"))
        evidence_ok = bool(evidence.get("digest"))
        authoritative = bool(success and executed and evidence_ok and result.get("status") in {"completed", "success"})
        objective_match = bool(success and executed)
        quality = "authoritative" if authoritative else "verified_internal" if evidence_ok else "missing"
        return {
            "authoritative": authoritative,
            "objective_match": objective_match,
            "evidence_quality": quality,
        }

    @staticmethod
    def _replace(run: AgentRun, **changes: Any) -> AgentRun:
        data = {
            "run_id": run.run_id,
            "organization_id": run.organization_id,
            "user_id": run.user_id,
            "instruction": run.instruction,
            "state": run.state,
            "classification": run.classification,
            "plan": run.plan,
            "simulation": run.simulation,
            "execution": run.execution,
            "decision": run.decision,
            "evidence": run.evidence,
            "outcome": run.outcome,
            "learning": run.learning,
            "next_action": run.next_action,
            "evidence_context_hash": run.evidence_context_hash,
        }
        data.update(changes)
        return AgentRun(**data)

    @staticmethod
    def _classification_dict(value: TaskClassification) -> dict[str, Any]:
        return {
            "task_type": value.task_type,
            "capabilities": sorted(value.capabilities),
            "risk": value.risk,
            "confidence": value.confidence,
        }

    @staticmethod
    def _digest(value: Any) -> str:
        payload = json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _run_id(instruction: str, organization_id: int) -> str:
        digest = hashlib.sha256(f"{organization_id}:{instruction}".encode("utf-8")).hexdigest()[:20]
        return f"agent-{digest}"


kemet_agent_runtime = KemetAgentRuntime()
