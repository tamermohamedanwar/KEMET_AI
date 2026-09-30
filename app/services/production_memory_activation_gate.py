from __future__ import annotations
from hashlib import sha256
import json
from typing import Any, Mapping

class ProductionMemoryActivationGate:
    SCHEMA = "kemet.production.memory_activation_gate.v1"

    @staticmethod
    def _digest(value: Mapping[str, Any]) -> str:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode()
        return sha256(raw).hexdigest()

    @classmethod
    def _finalize(cls, payload: dict[str, Any]) -> dict[str, Any]:
        payload["digest"] = cls._digest(payload)
        return payload

    def propose(self, *, organization_id: int, project_id: str, memory: Mapping[str, Any], lineage: Mapping[str, Any], reuse_assessment: Mapping[str, Any]) -> dict[str, Any]:
        if int(organization_id or 0) <= 0 or not project_id:
            raise ValueError("activation_binding_required")
        for value, label in ((memory, "memory"), (lineage, "lineage"), (reuse_assessment, "reuse_assessment")):
            if not isinstance(value, Mapping):
                raise ValueError(f"{label}_mapping_required")
        if any(x.get("organization_id") != int(organization_id) for x in (memory, lineage, reuse_assessment)):
            raise ValueError("organization_mismatch")
        if any(x.get("project_id") != str(project_id) for x in (memory, lineage, reuse_assessment)):
            raise ValueError("project_mismatch")
        if lineage.get("schema") != "kemet.production.memory_lineage.v1" or lineage.get("digest") != memory.get("lineage_digest"):
            raise ValueError("lineage_binding_invalid")
        if lineage.get("freshness", {}).get("status") != "FRESH" or not lineage.get("freshness", {}).get("verified_at"):
            raise ValueError("lineage_not_fresh")
        if reuse_assessment.get("memory_digest") != memory.get("digest") or reuse_assessment.get("planning_advisory") is not True:
            raise ValueError("reuse_assessment_invalid")
        return self._finalize({"schema": self.SCHEMA, "version": 1, "organization_id": int(organization_id), "project_id": str(project_id), "memory_digest": str(memory.get("digest") or ""), "lineage_digest": str(lineage.get("digest") or ""), "reuse_assessment_digest": str(reuse_assessment.get("digest") or ""), "status": "PENDING_HUMAN_ACTIVATION", "candidate_only": True, "planning_visible": False, "canonical_state_mutation": False, "policy_deployment_allowed": False, "authorization_issued": False, "execution_authority": False, "external_execution": False, "human_approval_required": True, "mcp": False})

    def decide(self, *, proposal: Mapping[str, Any], approver_id: int, decision: str) -> dict[str, Any]:
        if not isinstance(proposal, Mapping) or proposal.get("schema") != self.SCHEMA:
            raise ValueError("activation_proposal_invalid")
        if proposal.get("status") != "PENDING_HUMAN_ACTIVATION":
            raise ValueError("activation_not_pending")
        if int(approver_id or 0) <= 0:
            raise ValueError("approver_required")
        decision = str(decision or "").upper()
        if decision not in {"APPROVED", "REJECTED"}:
            raise ValueError("activation_decision_invalid")
        return self._finalize({"schema": "kemet.production.memory_activation_decision.v1", "version": 1, "organization_id": int(proposal["organization_id"]), "project_id": str(proposal["project_id"]), "proposal_digest": str(proposal["digest"]), "approver_id": int(approver_id), "decision": decision, "activated": decision == "APPROVED", "planning_visible": decision == "APPROVED", "authorization_issued": False, "execution_authority": False, "external_execution": False, "canonical_state_mutation": False, "policy_deployment_allowed": False, "mcp": False})

    def project(self, *, activation: Mapping[str, Any], memory: Mapping[str, Any], lineage: Mapping[str, Any]) -> dict[str, Any]:
        if not all(isinstance(x, Mapping) for x in (activation, memory, lineage)):
            raise ValueError("projection_mapping_required")
        if activation.get("schema") != "kemet.production.memory_activation_decision.v1" or activation.get("activated") is not True:
            raise ValueError("memory_not_activated")
        if activation.get("organization_id") != memory.get("organization_id") or activation.get("project_id") != memory.get("project_id"):
            raise ValueError("projection_binding_invalid")
        if activation.get("proposal_digest") == "":
            raise ValueError("activation_proposal_digest_required")
        if lineage.get("digest") != memory.get("lineage_digest") or lineage.get("freshness", {}).get("status") != "FRESH":
            raise ValueError("projection_lineage_invalid")
        return self._finalize({
            "schema": "kemet.production.memory_activation_record.v1", "version": 1,
            "organization_id": int(memory["organization_id"]), "project_id": str(memory["project_id"]),
            "memory_digest": str(memory["digest"]), "lineage_digest": str(lineage["digest"]),
            "activation_decision_digest": str(activation["digest"]),
            "status": "ACTIVATED", "planning_visible": True, "advisory_only": True,
            "canonical_state_mutation": False, "execution_authority": False,
            "external_execution": False, "policy_deployment_allowed": False, "mcp": False,
        })

    def revoke(self, *, activation_record: Mapping[str, Any], reason: str, actor_id: int) -> dict[str, Any]:
        if not isinstance(activation_record, Mapping) or activation_record.get("schema") != "kemet.production.memory_activation_record.v1":
            raise ValueError("activation_record_invalid")
        if not str(reason or "").strip() or int(actor_id or 0) <= 0:
            raise ValueError("revocation_metadata_required")
        return self._finalize({
            "schema": "kemet.production.memory_revocation_record.v1", "version": 1,
            "organization_id": int(activation_record["organization_id"]), "project_id": str(activation_record["project_id"]),
            "activation_record_digest": str(activation_record["digest"]), "actor_id": int(actor_id),
            "reason": str(reason), "status": "REVOKED", "planning_visible": False,
            "canonical_state_mutation": False, "execution_authority": False,
            "external_execution": False, "policy_deployment_allowed": False, "mcp": False,
        })

    def lifecycle_status(self, *, activation_record: Mapping[str, Any], lineage: Mapping[str, Any], now: str, revocation: Mapping[str, Any] | None = None, conflicts: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        if not isinstance(activation_record, Mapping) or activation_record.get("schema") != "kemet.production.memory_activation_record.v1":
            raise ValueError("activation_record_invalid")
        if not isinstance(lineage, Mapping) or lineage.get("schema") != "kemet.production.memory_lineage.v1":
            raise ValueError("lineage_invalid")
        if activation_record.get("lineage_digest") != lineage.get("digest"):
            raise ValueError("lifecycle_lineage_mismatch")
        if not str(now or "").strip():
            raise ValueError("lifecycle_time_required")
        if revocation is not None:
            return self._finalize({"schema":"kemet.production.memory_lifecycle_status.v1","version":1,"organization_id":int(activation_record["organization_id"]),"project_id":str(activation_record["project_id"]),"activation_record_digest":str(activation_record["digest"]),"status":"REVOKED","planning_visible":False,"reason":"revoked","observed_at":str(now),"advisory_only":True,"canonical_state_mutation":False,"execution_authority":False,"external_execution":False,"mcp":False})
        if lineage.get("freshness", {}).get("status") != "FRESH":
            return self._finalize({"schema":"kemet.production.memory_lifecycle_status.v1","version":1,"organization_id":int(activation_record["organization_id"]),"project_id":str(activation_record["project_id"]),"activation_record_digest":str(activation_record["digest"]),"status":"STALE","planning_visible":False,"reason":"lineage_not_fresh","observed_at":str(now),"advisory_only":True,"canonical_state_mutation":False,"execution_authority":False,"external_execution":False,"mcp":False})
        conflict_list = list(conflicts or [])
        if conflict_list:
            return self._finalize({"schema":"kemet.production.memory_lifecycle_status.v1","version":1,"organization_id":int(activation_record["organization_id"]),"project_id":str(activation_record["project_id"]),"activation_record_digest":str(activation_record["digest"]),"status":"CONFLICTED","planning_visible":False,"reason":"conflicting_evidence","conflict_digests":sorted(str(x.get("digest") or "") for x in conflict_list if isinstance(x, Mapping)),"observed_at":str(now),"advisory_only":True,"canonical_state_mutation":False,"execution_authority":False,"external_execution":False,"mcp":False})
        return self._finalize({"schema":"kemet.production.memory_lifecycle_status.v1","version":1,"organization_id":int(activation_record["organization_id"]),"project_id":str(activation_record["project_id"]),"activation_record_digest":str(activation_record["digest"]),"status":"ACTIVE","planning_visible":True,"reason":"fresh_and_unconflicted","observed_at":str(now),"advisory_only":True,"canonical_state_mutation":False,"execution_authority":False,"external_execution":False,"mcp":False})

    def planning_projection(self, *, activation_record: Mapping[str, Any], revocation: Mapping[str, Any] | None = None) -> dict[str, Any]:
        if not isinstance(activation_record, Mapping) or activation_record.get("schema") != "kemet.production.memory_activation_record.v1":
            raise ValueError("activation_record_invalid")
        if activation_record.get("status") != "ACTIVATED" or activation_record.get("planning_visible") is not True:
            raise ValueError("memory_not_activated")
        if revocation is not None:
            if not isinstance(revocation, Mapping):
                raise ValueError("revocation_mapping_required")
            if revocation.get("schema") != "kemet.production.memory_revocation_record.v1":
                raise ValueError("revocation_invalid")
            if revocation.get("activation_record_digest") != activation_record.get("digest"):
                raise ValueError("revocation_binding_invalid")
            raise ValueError("memory_revoked")
        return self._finalize({
            "schema": "kemet.production.memory_planning_projection.v1", "version": 1,
            "organization_id": int(activation_record["organization_id"]),
            "project_id": str(activation_record["project_id"]),
            "memory_digest": str(activation_record["memory_digest"]),
            "activation_record_digest": str(activation_record["digest"]),
            "status": "ACTIVE", "planning_visible": True, "advisory_only": True,
            "canonical_state_mutation": False, "execution_authority": False,
            "external_execution": False, "authorization_issued": False, "mcp": False,
        })

production_memory_activation_gate = ProductionMemoryActivationGate()
