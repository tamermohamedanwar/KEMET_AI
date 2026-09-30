from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Any, Mapping

from app.core.approval_package import ApprovalPackage, build_approval_package
from app.core.approval_decision import decide_approval
from app.core.central_gate_handoff import create_gate_handoff
from app.core.plan_context import PlanContext, bind_plan_context
from app.core.plan_risk import assess_plan_risk
from app.core.task_planner import PlannedStep, TaskPlan
from app.core.execution.authorization import execution_authorization


class GrowthExperimentApprovalBridgeService:
    """Binds a reviewed growth proposal to a deterministic approval-ready intent."""

    VERSION = "1.0"

    @classmethod
    def prepare(cls, *, organization_id: int, proposal: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_required")
        item = proposal or {}
        if not isinstance(item, Mapping):
            raise ValueError("proposal_required")
        channel = str(item.get("channel") or "").strip()
        body = item.get("proposal") or {}
        basis = item.get("basis") or {}
        if not channel or not isinstance(body, Mapping) or not isinstance(basis, Mapping):
            raise ValueError("proposal_binding_required")
        if int(basis.get("reconciled_content_count") or 0) <= 0:
            raise ValueError("reconciled_evidence_required")
        bindings = basis.get("evidence_bindings") or []
        if not isinstance(bindings, list) or not bindings:
            raise ValueError("evidence_bindings_required")
        normalized_bindings = []
        for binding in bindings:
            if not isinstance(binding, Mapping):
                raise ValueError("evidence_binding_invalid")
            required = ("content_id", "publication_id", "execution_key")
            if not all(str(binding.get(key) or "").strip() for key in required):
                raise ValueError("evidence_binding_invalid")
            if not str(binding.get("metric_evidence_digest") or "").strip():
                raise ValueError("evidence_binding_invalid")
            normalized_bindings.append({
                "content_id": str(binding.get("content_id")).strip(),
                "publication_id": str(binding.get("publication_id")).strip(),
                "execution_key": str(binding.get("execution_key")).strip(),
                "metric_evidence_digest": str(binding.get("metric_evidence_digest") or "").strip(),
            })
        if len(normalized_bindings) != int(basis.get("reconciled_content_count") or 0):
            raise ValueError("evidence_binding_count_mismatch")
        normalized_bindings.sort(key=lambda item: (item["content_id"], item["publication_id"], item["execution_key"]))
        intent = {
            "organization_id": int(organization_id),
            "action": "review_growth_experiment",
            "channel": channel,
            "objective": str(body.get("objective") or "controlled_growth_experiment"),
            "success_metric": str(body.get("success_metric") or "incremental_verified_revenue"),
            "guardrail": str(body.get("guardrail") or "do_not_treat_unverified_attribution_as_revenue"),
            "basis": {
                "verified_revenue": max(0.0, float(basis.get("verified_revenue") or 0)),
                "qualified_views": max(0.0, float(basis.get("qualified_views") or 0)),
                "reconciled_content_count": int(basis.get("reconciled_content_count") or 0),
                "evidence_bindings": normalized_bindings,
            },
        }
        digest = hashlib.sha256(json.dumps(intent, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return {
            "success": True,
            "engine": "kemet_growth_experiment_approval_bridge",
            "version": cls.VERSION,
            "approval_status": "approval_required",
            "execution_requested": False,
            "intent": intent,
            "intent_hash": digest,
            "governance": {
                "read_only": True,
                "tenant_scoped": True,
                "database_mutation": False,
                "external_execution": False,
                "execution_authority": False,
                "human_approval_required": True,
                "financial_action": False,
                "causal_claim": False,
                "roi_claim": False,
            },
        }

    @classmethod
    def prepare_approval_package(cls, *, organization_id: int, proposal: Mapping[str, Any] | None = None, user_id: int | None = None) -> dict[str, Any]:
        prepared = cls.prepare(organization_id=organization_id, proposal=proposal)
        intent = prepared["intent"]
        task_id = f"growth-experiment-{prepared['intent_hash'][:16]}"
        governed_action = {
            "facebook": "facebook_publish",
            "instagram": "instagram_publish",
        }.get(str(intent["channel"]).lower())
        if not governed_action:
            raise ValueError("governed_growth_action_required")
        step = PlannedStep(
            step_id="growth_experiment",
            objective=intent["objective"],
            action=governed_action,
            risk="high",
            requires_approval=True,
            capabilities=frozenset({"growth_experiment", "revenue_intelligence"}),
            parameters={"intent_hash": prepared["intent_hash"], "intent": intent},
        )
        plan_payload = {
            "task_id": task_id,
            "organization_id": int(organization_id),
            "task_type": "automation",
            "risk": "high",
            "steps": [asdict(step)],
        }
        plan_hash = hashlib.sha256(json.dumps(plan_payload, sort_keys=True, default=str).encode()).hexdigest()
        plan = TaskPlan(task_id, int(organization_id), "automation", "high", 1.0, (step,), True, plan_hash)
        context = PlanContext(organization_id=int(organization_id), user_id=int(user_id) if user_id is not None else None, metadata={"surface": "revenue_center", "intent_hash": prepared["intent_hash"]})
        binding = bind_plan_context(plan, context)
        assessment = assess_plan_risk(plan)
        package = build_approval_package(plan, binding, assessment, evidence_context_hash=prepared["intent_hash"])
        return {**prepared, "approval_package": package.as_dict(), "plan": plan.as_dict(), "context": binding, "risk_assessment": assessment.as_dict(), "execution_requested": False, "governance": {**prepared["governance"], "approval_package_bound": True}}

    @classmethod
    def approve_to_gate(
        cls,
        *,
        organization_id: int,
        package_payload: Mapping[str, Any],
        plan: Mapping[str, Any],
        approver_id: int,
        approved: bool,
        reason: str = "",
        action: str,
        execution_key: str,
    ) -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_required")
        if not isinstance(package_payload, Mapping) or not isinstance(plan, Mapping):
            raise ValueError("approval_binding_required")
        package = cls._package_from_payload(package_payload)
        if not approved:
            decision = decide_approval(package, int(approver_id), False, reason)
            return {"success": True, "status": "rejected", "decision": decision.as_dict(), "gate_handoff": None}
        clean_action = str(action or "").strip()
        clean_key = str(execution_key or "").strip()
        if not clean_action or not clean_key:
            raise ValueError("gate_binding_required")
        from app.automation.action_registry import registry
        if not registry.exists(clean_action):
            raise ValueError("action_not_governed")
        if package.organization_id != int(organization_id):
            raise ValueError("tenant_context_mismatch")
        if str(plan.get("plan_hash") or "") != package.plan_hash:
            raise ValueError("approval_plan_mismatch")
        steps = plan.get("steps") or []
        planned_action = str((steps[0] or {}).get("action") or "") if isinstance(steps, list) and steps else str(plan.get("action") or "")
        if clean_action != planned_action:
            raise ValueError("approval_action_mismatch")
        decision = decide_approval(package, int(approver_id), True, reason)
        handoff = create_gate_handoff(package, decision, action=clean_action, execution_key=clean_key)
        return {
            "success": True,
            "status": "approved_for_gate",
            "decision": decision.as_dict(),
            "gate_handoff": handoff.as_dict(),
            "execution_requested": False,
            "one_time_authorization_required": True,
            "governance": {
                "human_approval_verified": True,
                "external_execution": False,
                "financial_action": False,
                "execution_authority": False,
                "fail_closed_unknown_action": True,
            },
        }

    @classmethod
    def issue_one_time_authorization(
        cls,
        *,
        organization_id: int,
        plan: Mapping[str, Any],
        gate_handoff: Mapping[str, Any],
    ) -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_required")
        if not isinstance(plan, Mapping) or not isinstance(gate_handoff, Mapping):
            raise ValueError("gate_handoff_binding_required")
        if int(plan.get("organization_id") or 0) != int(organization_id):
            raise ValueError("tenant_context_mismatch")
        from app.core.central_gate_handoff import GateHandoff
        try:
            handoff = GateHandoff(**dict(gate_handoff))
        except (TypeError, ValueError) as exc:
            raise ValueError("gate_handoff_invalid") from exc
        result = execution_authorization.create_handoff_authorization(dict(plan), handoff)
        if result.get("authorized") is not True:
            raise ValueError(str(result.get("error") or "execution_authorization_denied"))
        result["gate_handoff"] = handoff.as_dict()
        from app.core.federation.execution_envelope import execution_envelope
        result["execution_envelope"] = execution_envelope.build(
            approval_package_hash=handoff.package_hash,
            decision_hash=handoff.decision_hash,
            handoff_hash=handoff.handoff_hash,
            authorization=result,
            execution_key=handoff.execution_key,
            provider_id="kemet",
            action=handoff.action,
            evidence_context_hash=str(plan.get("evidence_context_hash") or ""),
        )
        return {
            "success": True,
            "authorization": result,
            "execution_requested": False,
            "one_time": True,
            "governance": {
                "human_approval_verified": True,
                "authorization_source": "human_approval",
                "external_execution": False,
                "execution_authority": False,
                "single_use": True,
            },
        }

    @classmethod
    def execute_authorized_dry_run(
        cls,
        *,
        organization_id: int,
        plan: Mapping[str, Any],
        authorization: Mapping[str, Any],
        user_id: int | None = None,
    ) -> dict[str, Any]:
        if int(organization_id) <= 0:
            raise ValueError("organization_required")
        if not isinstance(plan, Mapping) or not isinstance(authorization, Mapping):
            raise ValueError("execution_binding_required")
        if int(plan.get("organization_id") or 0) != int(organization_id):
            raise ValueError("tenant_context_mismatch")
        auth = dict(authorization)
        if not auth.get("gate_handoff"):
            raise ValueError("gate_handoff_required")
        if auth.get("authorization_source") != "human_approval":
            raise ValueError("human_approval_authorization_required")
        from app.core.execution.runtime import canonical_execution_runtime
        from app.automation.action_registry import registry
        action = str(auth.get("action") or "").strip()
        if action not in {"facebook_publish", "instagram_publish"}:
            raise ValueError("action_not_governed")
        execution_plan = dict(plan)
        envelope = auth.get("execution_envelope")
        handoff = auth.get("gate_handoff") or {}
        if not isinstance(envelope, dict) or not isinstance(handoff, dict):
            raise ValueError("execution_envelope_required")
        execution_plan.update({
            "execution_key": str(auth.get("execution_key") or handoff.get("execution_key") or ""),
            "provider_id": "kemet",
            "approval_package_hash": str(handoff.get("package_hash") or ""),
            "decision_hash": str(handoff.get("decision_hash") or ""),
            "central_gate_handoff_hash": str(handoff.get("handoff_hash") or ""),
            "evidence_context_hash": str(plan.get("evidence_context_hash") or ""),
            "execution_envelope": envelope,
        })
        parameters = dict(plan.get("parameters") or {})
        parameters.update({
            "organization_id": int(organization_id),
            "user_id": int(user_id or 0),
            "channel": "instagram" if action == "instagram_publish" else "facebook",
            "dry_run": True,
            "publication_approval": True,
            "asset_uri": str(parameters.get("asset_uri") or "dry-run://growth-experiment"),
            "media_type": str(parameters.get("media_type") or "image"),
            "caption": str(parameters.get("caption") or "Kemet governed growth experiment dry run"),
            "idempotency_key": str(parameters.get("idempotency_key") or auth.get("execution_key") or ""),
        })
        auth["execution_parameters"] = parameters
        result = canonical_execution_runtime.execute(
            plan=execution_plan,
            authorization=auth,
            action_registry=registry,
            user_id=user_id,
        )
        return {
            "success": bool(result.get("success")),
            "status": "dry_run_completed" if result.get("success") else result.get("status", "blocked"),
            "execution_requested": True,
            "external_execution": False,
            "real_publication": False,
            "result": result,
            "governance": {
                "human_approval_verified": True,
                "canonical_runtime": True,
                "dry_run": True,
                "one_time_authorization_consumed": bool(result.get("executed")),
                "external_execution": False,
            },
        }

    @staticmethod
    def _package_from_payload(payload: Mapping[str, Any]) -> ApprovalPackage:
        return ApprovalPackage(
            organization_id=int(payload.get("organization_id") or 0),
            plan_hash=str(payload.get("plan_hash") or ""),
            context_fingerprint=str(payload.get("context_fingerprint") or ""),
            risk_level=str(payload.get("risk_level") or ""),
            risk_score=int(payload.get("risk_score") or 0),
            approval_required=bool(payload.get("approval_required")),
            external_side_effects=bool(payload.get("external_side_effects")),
            database_mutation=bool(payload.get("database_mutation")),
            affected_resources=tuple(str(x) for x in payload.get("affected_resources") or ()),
            reasons=tuple(str(x) for x in payload.get("reasons") or ()),
            evidence_requirements=tuple(str(x) for x in payload.get("evidence_requirements") or ()),
            package_hash=str(payload.get("package_hash") or ""),
            evidence_context_hash=str(payload.get("evidence_context_hash") or ""),
        )


growth_experiment_approval_bridge_service = GrowthExperimentApprovalBridgeService()
