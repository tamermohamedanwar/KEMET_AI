from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from app.core.evidence.fabric import execution_evidence_fabric
from app.core.federation_policy import federation_policy
from app.core.provider_factory import federated_generate
from app.services.kemet_provenance_lineage_service import kemet_provenance_lineage_service


class ProviderDecisionIntelligenceService:
    VERSION = "1.1"
    SCHEMA = "kemet.provider_decision_intelligence.v1"
    DECISION_RECORD_SCHEMA = "kemet.provider_decision_record.v1"

    @staticmethod
    def _digest(value: Any) -> str:
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _safe_input(bi: dict[str, Any]) -> dict[str, Any]:
        decision = bi.get("decision") or {}
        return {
            "schema": bi.get("schema"),
            "lead_id": bi.get("lead_id"),
            "score": bi.get("score", {}).get("score"),
            "segment": bi.get("segment", {}).get("segment"),
            "qualification": bi.get("qualification", {}).get("status"),
            "confidence": bi.get("confidence"),
            "missing_data": bi.get("missing_data", []),
            "decision": decision.get("decision"),
            "rationale": decision.get("rationale"),
            "recommended_next_step": decision.get("recommended_next_step"),
            "evidence": decision.get("evidence", []),
        }

    @classmethod
    def build_prompt(cls, bi: dict[str, Any]) -> str:
        safe = cls._safe_input(bi)
        return (
            "Review this governed business-intelligence decision as advisory intelligence only. "
            "Do not execute actions, invent missing facts, or claim certainty. "
            "Return concise JSON-like text with assessment, risks, missing_information, "
            "and recommended_review_points. Input:\n" + json.dumps(safe, sort_keys=True, ensure_ascii=False)
        )

    @classmethod
    def analyze(cls, bi: dict[str, Any], *, organization_id: int | None = None,
                preferred: str | None = None, model: str | None = None) -> dict[str, Any]:
        if not isinstance(bi, dict):
            raise ValueError("business_intelligence_required")
        tenant_id = bi.get("tenant_id")
        if tenant_id is None:
            raise ValueError("tenant_id_required")
        if organization_id is not None and int(organization_id) != int(tenant_id):
            raise ValueError("tenant_mismatch")
        organization_id = int(tenant_id if organization_id is None else organization_id)
        policy = federation_policy.for_organization(organization_id)
        safe_input = cls._safe_input(bi)
        input_digest = cls._digest(safe_input)
        prompt = cls.build_prompt(bi)
        started = time.perf_counter()
        response = federated_generate(
            prompt,
            system="You are a governed advisory decision reviewer. Never execute external actions.",
            model=model,
            preferred=preferred,
            required_capabilities={"reasoning"},
            organization_id=organization_id,
        )
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        output_digest = cls._digest({"content": response.content, "provider": response.provider_id, "model": response.model})
        metadata = getattr(response, "metadata", None) or {}
        observed_cost = metadata.get("cost_usd")
        if observed_cost is not None:
            observed_cost = max(0.0, float(observed_cost))
        request_identity = str(getattr(response, "request_id", None) or output_digest[:16])
        provider_node = {
            "type": "source",
            "id": f"provider-request:{response.provider_id}:{request_identity}",
            "organization_id": organization_id,
            "version": 1,
            "digest": cls._digest({"provider": response.provider_id, "model": response.model, "request_id": getattr(response, "request_id", None), "input_digest": input_digest, "output_digest": output_digest}),
            "metadata": {"provider": response.provider_id, "model": response.model, "request_id": getattr(response, "request_id", None), "cost_status": "observed" if observed_cost is not None else "not_observed"},
        }
        provenance = kemet_provenance_lineage_service.build_chain(
            organization_id=organization_id,
            trace_id=request_identity,
            nodes=[provider_node],
        )
        evidence_digest = execution_evidence_fabric.digest({
            "schema": cls.SCHEMA, "version": cls.VERSION, "tenant_id": tenant_id,
            "lead_id": bi.get("lead_id"), "input_digest": input_digest,
            "output_digest": output_digest, "provider": response.provider_id,
            "model": response.model, "confidence": float(bi.get("confidence") or 0.0),
        })
        decision_record_payload = {
            "schema": cls.DECISION_RECORD_SCHEMA,
            "version": 1,
            "organization_id": organization_id,
            "lead_id": bi.get("lead_id"),
            "provider": response.provider_id,
            "model": response.model,
            "request_id": getattr(response, "request_id", None),
            "input_digest": input_digest,
            "output_digest": output_digest,
            "evidence_digest": evidence_digest,
            "provenance_digest": provenance["digest"],
            "cost_status": "observed" if observed_cost is not None else "not_observed",
            "status": "review_required",
            "governance": {
                "advisory": True,
                "read_only": True,
                "external_execution": False,
                "auto_execute": False,
                "human_approval_required": True,
            },
        }
        decision_record = {**decision_record_payload, "digest": cls._digest(decision_record_payload)}
        control_chain = execution_evidence_fabric.control_chain(
            correlation=execution_evidence_fabric.correlation_context(
                trace_id=request_identity, organization_id=organization_id,
                evidence_id=evidence_digest,
            ),
            stages=[
                {"stage": "decision", "status": "review_required", "id": decision_record["digest"]},
                {"stage": "approval", "status": "pending", "id": None},
                {"stage": "execution", "status": "not_executed", "id": None},
                {"stage": "evidence", "status": "observed", "id": evidence_digest},
            ],
        )
        return {
            "schema": cls.SCHEMA,
            "version": cls.VERSION,
            "tenant_id": tenant_id,
            "lead_id": bi.get("lead_id"),
            "provider": response.provider_id,
            "model": response.model,
            "input_digest": input_digest,
            "output_digest": output_digest,
            "evidence_digest": evidence_digest,
            "provenance_lineage": provenance,
            "decision_record": decision_record,
            "control_evidence_chain": control_chain,
            "content": response.content,
            "confidence": float(bi.get("confidence") or 0.0),
            "evidence": bi.get("decision", {}).get("evidence", []),
            "missing_data": bi.get("missing_data", []),
            "latency_ms": latency_ms,
            "cost": observed_cost,
            "cost_status": "observed" if observed_cost is not None else "not_observed",
            "tokens": {"input": response.input_tokens, "output": response.output_tokens, "total": response.total_tokens},
            "policy": {"organization_id": policy.organization_id, "provider_allowed": policy.provider_allowed(response.provider_id), "model_allowed": policy.model_allowed(response.model)},
            "governance": {"advisory": True, "read_only": True, "external_execution": False, "auto_execute": False, "human_approval_required": True},
        }


provider_decision_intelligence = ProviderDecisionIntelligenceService()
