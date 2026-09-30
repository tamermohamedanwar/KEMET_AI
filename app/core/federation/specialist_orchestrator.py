from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from app.core.execution.execution_boundary import execution_boundary
from app.core.execution.authorization import execution_authorization
from app.core.execution_evidence import execution_evidence
from app.core.execution_ledger import execution_ledger
from app.core.federation.routing_preview import federation_routing_preview
from app.core.federation.specialist_contracts import SpecialistRequest, SpecialistResponse
from app.core.federation.specialist_registry import specialist_registry
from app.core.federation.execution_envelope import execution_envelope


@dataclass(frozen=True)
class SpecialistExecutionResult:
    success: bool
    executed: bool
    provider_id: str | None
    status: str
    task_id: str
    external_task_id: str | None = None
    request_id: str | None = None
    content: str | None = None
    error: str | None = None
    evidence: tuple[dict[str, Any], ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class SpecialistOrchestrator:
    VERSION = "1.0"

    def _authorization_result(
        self,
        plan: Mapping[str, Any],
        authorization: Mapping[str, Any],
        action: str,
    ) -> dict[str, Any]:
        return execution_boundary.require(dict(plan), dict(authorization), action)

    def execute(
        self,
        *,
        prompt: str,
        plan: Mapping[str, Any],
        authorization: Mapping[str, Any],
        organization_id: int,
        user_id: int,
        task_id: str,
        verified_provider_ids: set[str],
        preferred_provider: str | None = None,
        capabilities: tuple[str, ...] = (),
        model: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        execution_envelope_payload: Mapping[str, Any] | None = None,
    ) -> SpecialistExecutionResult:
        if not prompt.strip():
            return SpecialistExecutionResult(False, False, None, "blocked", task_id, error="prompt_required")
        if organization_id <= 0 or user_id <= 0:
            return SpecialistExecutionResult(False, False, None, "blocked", task_id, error="execution_scope_required")
        action = str(plan.get("action") or "").strip()
        if not action:
            return SpecialistExecutionResult(False, False, None, "blocked", task_id, error="execution_action_required")
        if not verified_provider_ids:
            return SpecialistExecutionResult(False, False, None, "blocked", task_id, error="verified_specialist_required")

        routing = federation_routing_preview.preview(
            prompt, organization_id=organization_id, verified_provider_ids=verified_provider_ids
        )
        specialist = routing.specialist
        if not specialist:
            return SpecialistExecutionResult(False, False, None, "unavailable", task_id, error="specialist_unavailable")
        provider_id = str(specialist["provider_id"])
        if preferred_provider and provider_id != preferred_provider:
            return SpecialistExecutionResult(False, False, provider_id, "route_changed", task_id, error="specialist_route_mismatch")
        adapter = specialist_registry.get(provider_id)
        if adapter is None:
            return SpecialistExecutionResult(False, False, provider_id, "blocked", task_id, error="specialist_adapter_missing")

        gate = self._authorization_result(plan, authorization, action)
        if not gate.get("allowed"):
            return SpecialistExecutionResult(False, False, provider_id, "blocked", task_id, error=str(gate.get("error") or "central_gate_blocked"))

        execution_key = str(plan.get("execution_key") or task_id)
        effective_plan_hash = str(plan.get("plan_hash") or authorization.get("plan_hash") or "")
        envelope = execution_envelope_payload or plan.get("execution_envelope")
        if not isinstance(envelope, Mapping) or not execution_envelope.verify(
            envelope, authorization=authorization, execution_key=execution_key,
            provider_id=provider_id, action=action,
            approval_package_hash=str(plan.get("approval_package_hash") or "") or None,
            decision_hash=str(plan.get("decision_hash") or "") or None,
            handoff_hash=str(plan.get("central_gate_handoff_hash") or "") or None,
            evidence_context_hash=str(plan.get("evidence_context_hash") or "") or None,
            outcome_contract_digest=str(plan.get("outcome_contract_digest") or "") or None,
            artifact_preview_digest=str(plan.get("artifact_preview_digest") or "") or None,
        ):
            return SpecialistExecutionResult(False, False, provider_id, "blocked", task_id, error="execution_envelope_invalid")
        if not effective_plan_hash:
            return SpecialistExecutionResult(False, False, provider_id, "blocked", task_id, error="plan_identity_required")

        request = SpecialistRequest(
            organization_id=organization_id,
            task_id=task_id,
            prompt=prompt,
            capabilities=tuple(capabilities or routing.capabilities),
            model=model,
            context_fingerprint=str(plan.get("context_fingerprint") or "") or None,
            metadata={**dict(metadata or {}), "execution_key": execution_key,
                      "trace_id": str((metadata or {}).get("trace_id") or ""),
                      "correlation_id": str((metadata or {}).get("correlation_id") or "")},
        )

        if not hasattr(adapter, "submit"):
            return SpecialistExecutionResult(False, False, provider_id, "unsupported", task_id, error="specialist_execution_not_supported")

        if not execution_authorization.consume(dict(authorization), plan=dict(plan), action=action):
            return SpecialistExecutionResult(False, False, provider_id, "blocked", task_id, error="execution_authorization_used")

        execution_ledger.begin(
            organization_id=organization_id, execution_key=execution_key,
            plan_hash=effective_plan_hash, approval_hash=str(plan.get("approval_package_hash") or "") or None,
            decision_hash=str(plan.get("decision_hash") or "") or None,
            trace_id=str((metadata or {}).get("trace_id") or "") or None,
            correlation_id=str((metadata or {}).get("correlation_id") or "") or None,
        )
        execution_evidence.record(
            organization_id=organization_id,
            execution_key=execution_key,
            stage="specialist.execution_started",
            status="authorized",
            evidence_key=f"{execution_key}:specialist.execution_started",
            plan_hash=effective_plan_hash,
            receipt={"provider_id": provider_id, "action": action},
        )
        try:
            response: SpecialistResponse = adapter.submit(
                request, plan=dict(plan), authorization=dict(authorization)
            )
        except Exception as exc:
            execution_ledger.finish(
                organization_id=organization_id, execution_key=execution_key, status="failed",
                receipt={"provider_id": provider_id, "action": action, "error": type(exc).__name__},
            )
            execution_evidence.record(
                organization_id=organization_id,
                execution_key=execution_key,
                stage="specialist.execution_failed",
                status="failed",
                evidence_key=f"{execution_key}:specialist.execution_failed",
                plan_hash=effective_plan_hash,
                receipt={"provider_id": provider_id, "error": type(exc).__name__},
            )
            return SpecialistExecutionResult(False, True, provider_id, "failed", task_id, error=str(exc))

        execution_ledger.finish(
            organization_id=organization_id, execution_key=execution_key, status=str(response.status),
            receipt={"provider_id": provider_id, "action": action,
                     "external_task_id": response.external_task_id, "request_id": response.request_id,
                     "status": response.status},
        )
        execution_evidence.record(
            organization_id=organization_id,
            execution_key=execution_key,
            stage="specialist.execution_submitted",
            status=response.status,
            evidence_key=f"{execution_key}:specialist.execution_submitted",
            plan_hash=effective_plan_hash,
            receipt={"provider_id": provider_id, "external_task_id": response.external_task_id,
                     "request_id": response.request_id},
        )
        return SpecialistExecutionResult(
            True, True, provider_id, response.status, task_id,
            response.external_task_id, response.request_id, response.content,
            evidence=(
                {"stage": "specialist.execution_started", "status": "authorized"},
                {"stage": "specialist.execution_submitted", "status": response.status},
            ),
        )


specialist_orchestrator = SpecialistOrchestrator()
