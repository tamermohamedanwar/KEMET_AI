"""Canonical Production Intelligence contracts over the existing production graph.
This layer records production state, memory, trajectory, specification, and bounded
policy proposals without becoming a second runtime or executor.
"""
from __future__ import annotations
from hashlib import sha256
import json
from typing import Any, Mapping

from app.services.production_memory_activation_gate import production_memory_activation_gate
from app.services.production_learning_trace_gate import production_learning_trace_gate

class ProductionIntelligence:
    VERSION = "1.0"
    SCHEMAS = {
        "state": "kemet.production.intelligence_state.v1",
        "memory": "kemet.production.memory.v1",
        "trajectory": "kemet.production.trajectory.v1",
        "specification": "kemet.production.specification.v1",
        "policy_proposal": "kemet.production.policy_proposal.v1",
        "memory_lineage": "kemet.production.memory_lineage.v1",
    }

    @staticmethod
    def _org(value: Any) -> None:
        if int(value or 0) <= 0:
            raise ValueError("organization_required")

    @staticmethod
    def _mapping(value: Any, label: str) -> None:
        if not isinstance(value, Mapping):
            raise ValueError(f"{label}_mapping_required")

    @staticmethod
    def _digest(value: Mapping[str, Any]) -> str:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"), default=str).encode()
        return sha256(raw).hexdigest()

    @classmethod
    def _finalize(cls, payload: dict[str, Any]) -> dict[str, Any]:
        payload["digest"] = cls._digest(payload)
        return payload

    @staticmethod
    def _governance() -> dict[str, Any]:
        return {
            "execution_authority": False,
            "external_execution": False,
            "human_approval_required": True,
            "mcp": False,
        }

    def state(self, *, organization_id: int,
              production_state: Mapping[str, Any],
              graph: Mapping[str, Any]) -> dict[str, Any]:
        self._org(organization_id)
        self._mapping(production_state, "production_state")
        self._mapping(graph, "production_graph")
        return self._finalize({
            "schema": self.SCHEMAS["state"],
            "version": 1,
            "organization_id": int(organization_id),
            "production_state_digest": str(production_state.get("digest") or ""),
            "production_graph_digest": str(graph.get("digest") or ""),
            "canonical": True,
            "source_of_truth": "canonical_production_state",
            "typed_domains": [
                "narrative", "characters", "world", "cinematic", "assets",
                "shots", "continuity", "audio", "editorial", "compute",
                "qa", "repair", "approval", "provenance", "outcomes",
            ],
            "prompt_policy": "prompts_are_derived_artifacts",
            "governance": self._governance(),
        })

    def memory_lineage(self, *, organization_id: int, project_id: str, impact_digest: str, evaluation_gate_digest: str, trajectory_digest: str, replay_digest: str, evidence_digests: list[str], freshness: Mapping[str, Any], source_of_truth: str = "canonical_production_state") -> dict[str, Any]:
        self._org(organization_id)
        if not project_id or not impact_digest or not evaluation_gate_digest or not trajectory_digest or not replay_digest:
            raise ValueError("memory_lineage_binding_required")
        if not isinstance(evidence_digests, list) or len({str(x) for x in evidence_digests if str(x)}) < 3:
            raise ValueError("memory_lineage_evidence_required")
        self._mapping(freshness, "freshness")
        if freshness.get("status") != "FRESH" or not freshness.get("verified_at"):
            raise ValueError("memory_lineage_freshness_not_verified")
        normalized = sorted({str(x) for x in evidence_digests if str(x)})
        return self._finalize({
            "schema": self.SCHEMAS["memory_lineage"], "version": 1,
            "organization_id": int(organization_id), "project_id": str(project_id),
            "impact_digest": str(impact_digest), "evaluation_gate_digest": str(evaluation_gate_digest),
            "trajectory_digest": str(trajectory_digest), "replay_digest": str(replay_digest),
            "evidence_digests": normalized, "freshness": dict(freshness),
            "source_of_truth": str(source_of_truth), "immutable": True,
            "canonical_state_mutation": False, "policy_deployment_allowed": False,
            "planning_advisory_only": True, "governance": self._governance(),
        })

    def memory(self, *, organization_id: int, project_id: str,
               facts: list[Mapping[str, Any]],
               invariants: list[Mapping[str, Any]],
               failure_patterns: list[Mapping[str, Any]],
               evidence_digests: list[str]) -> dict[str, Any]:
        self._org(organization_id)
        if not project_id:
            raise ValueError("project_required")
        for item in (facts, invariants, failure_patterns):
            if not isinstance(item, list):
                raise ValueError("memory_collection_required")
            if not all(isinstance(x, Mapping) for x in item):
                raise ValueError("memory_item_mapping_required")
        if not isinstance(evidence_digests, list):
            raise ValueError("evidence_digests_required")
        return self._finalize({
            "schema": self.SCHEMAS["memory"], "version": 1,
            "organization_id": int(organization_id), "project_id": str(project_id),
            "facts": [dict(x) for x in facts],
            "approved_invariants": [dict(x) for x in invariants],
            "failure_patterns": [dict(x) for x in failure_patterns],
            "evidence_digests": [str(x) for x in evidence_digests],
            "canonical": True, "canonical_state_mutation": False,
            "source_of_truth": "canonical_production_state",
            "reusable": True, "evidence_backed": bool(evidence_digests),
            "governance": self._governance(),
        })
    def trajectory(self, *, organization_id: int, project_id: str,
                    events: list[Mapping[str, Any]],
                    outcome: Mapping[str, Any],
                    canonical_state_digest: str) -> dict[str, Any]:
        self._org(organization_id)
        if not project_id or not canonical_state_digest:
            raise ValueError("trajectory_binding_required")
        if not isinstance(events, list) or not all(isinstance(x, Mapping) for x in events):
            raise ValueError("trajectory_events_required")
        self._mapping(outcome, "outcome")
        normalized = []
        for index, event in enumerate(events):
            item = dict(event)
            item.setdefault("sequence", index)
            if "evidence_digest" not in item:
                item["evidence_digest"] = ""
            normalized.append(item)
        return self._finalize({
            "schema": self.SCHEMAS["trajectory"], "version": 1,
            "organization_id": int(organization_id), "project_id": str(project_id),
            "canonical_state_digest": str(canonical_state_digest),
            "events": normalized, "outcome": dict(outcome),
            "event_digest": self._digest({"events": normalized}),
            "replayable": True,
            "evidence_backed": all(bool(x.get("evidence_digest")) for x in normalized)
                if normalized else False,
            "canonical": True,
            "source_of_truth": "canonical_production_trajectory",
            "governance": self._governance(),
        })

    def specification(self, *, organization_id: int, project_id: str,
                      scenes: list[Mapping[str, Any]],
                      shots: list[Mapping[str, Any]],
                      assets: list[Mapping[str, Any]],
                      constraints: list[Mapping[str, Any]],
                      production_profile: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._org(organization_id)
        if not project_id:
            raise ValueError("project_required")
        collections = (scenes, shots, assets, constraints)
        if not all(isinstance(x, list) for x in collections):
            raise ValueError("specification_collection_required")
        if not all(isinstance(item, Mapping) for coll in collections for item in coll):
            raise ValueError("specification_item_mapping_required")
        return self._finalize({
            "schema": self.SCHEMAS["specification"], "version": 1,
            "organization_id": int(organization_id), "project_id": str(project_id),
            "scenes": [dict(x) for x in scenes],
            "shots": [dict(x) for x in shots],
            "assets": [dict(x) for x in assets],
            "constraints": [dict(x) for x in constraints],
            "production_profile": dict(production_profile or {}),
            "provider_independent": True,
            "compiles_to": [
                "SCENE_PLAN", "SHOT_GRAPH", "ASSET_PLAN", "VOICE_PLAN",
                "RENDER_PLAN", "QA_PLAN",
            ],
            "prompts_are_derived": True,
            "human_review_required": True,
            "canonical": True,
            "source_of_truth": "canonical_production_state",
            "governance": self._governance(),
        })
    def propose_policy(self, *, organization_id: int, project_id: str,
                       stage: str, patch: Mapping[str, Any],
                       trajectory_digest: str, replay_digest: str,
                       paired_evaluation: Mapping[str, Any]) -> dict[str, Any]:
        self._org(organization_id)
        if not project_id or not stage:
            raise ValueError("policy_binding_required")
        self._mapping(patch, "patch")
        self._mapping(paired_evaluation, "paired_evaluation")
        if not trajectory_digest or not replay_digest:
            raise ValueError("evidence_replay_required")
        return self._finalize({
            "schema": self.SCHEMAS["policy_proposal"], "version": 1,
            "organization_id": int(organization_id), "project_id": str(project_id),
            "stage": str(stage), "patch": dict(patch),
            "trajectory_digest": str(trajectory_digest),
            "structural_replay_digest": str(replay_digest),
            "paired_evaluation": dict(paired_evaluation),
            "bounded_stage_local": True,
            "requires_structural_replay": True,
            "requires_paired_evaluation": True,
            "human_approval_required": True,
            "auto_deploy": False,
            "canonical_state_mutation": False,
            "canonical": True,
            "source_of_truth": "canonical_production_trajectory",
            "governance": self._governance(),
        })


    def bind_graph_trajectory(self, *, organization_id: int, project_id: str, graph: Mapping[str, Any], node_evidence: Mapping[str, Mapping[str, Any]] | None = None, outcome: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._org(organization_id)
        if not project_id:
            raise ValueError("project_required")
        self._mapping(graph, "production_graph")
        if graph.get("organization_id") != int(organization_id):
            raise ValueError("organization_mismatch")
        if graph.get("project_id") != str(project_id):
            raise ValueError("project_mismatch")
        nodes = graph.get("nodes")
        if not isinstance(nodes, list) or not isinstance(graph.get("edges"), list):
            raise ValueError("production_graph_structure_required")
        evidence = node_evidence or {}
        events = []
        for index, node in enumerate(nodes):
            if not isinstance(node, Mapping):
                raise ValueError("production_graph_node_mapping_required")
            node_id = str(node.get("id") or "")
            if not node_id:
                raise ValueError("production_graph_node_id_required")
            node_ev = evidence.get(node_id) or {}
            events.append({"sequence": index, "node_id": node_id, "kind": str(node.get("kind") or ""), "status": str(node.get("status") or ""), "evidence_digest": str(node_ev.get("digest") or ""), "input_digest": str(node_ev.get("input_digest") or ""), "output_digest": str(node_ev.get("output_digest") or "")})
        return self.trajectory(organization_id=organization_id, project_id=project_id, events=events, outcome=dict(outcome or {}), canonical_state_digest=str(graph.get("state_digest") or ""))

    def memory_from_trajectory(self, *, organization_id: int, project_id: str, trajectory: Mapping[str, Any], facts: list[Mapping[str, Any]] | None = None, invariants: list[Mapping[str, Any]] | None = None, failure_patterns: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        self._org(organization_id)
        self._mapping(trajectory, "trajectory")
        if trajectory.get("organization_id") != int(organization_id) or trajectory.get("project_id") != str(project_id):
            raise ValueError("trajectory_binding_required")
        events = trajectory.get("events")
        if not isinstance(events, list):
            raise ValueError("trajectory_events_required")
        evidence = [str(item.get("evidence_digest")) for item in events if isinstance(item, Mapping) and item.get("evidence_digest")]
        return self.memory(organization_id=organization_id, project_id=project_id, facts=list(facts or []), invariants=list(invariants or []), failure_patterns=list(failure_patterns or []), evidence_digests=evidence)

    def plan_context(self, *, organization_id: int, project_id: str, specification: Mapping[str, Any], memory: Mapping[str, Any], reuse_assessment: Mapping[str, Any] | None = None, memory_planning_projection: Mapping[str, Any] | None = None, memory_lifecycle_status: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._org(organization_id)
        self._mapping(specification, "specification")
        self._mapping(memory, "memory")
        if specification.get("organization_id") != int(organization_id) or memory.get("organization_id") != int(organization_id):
            raise ValueError("organization_mismatch")
        if specification.get("project_id") != str(project_id) or memory.get("project_id") != str(project_id):
            raise ValueError("project_mismatch")
        if memory.get("reusable") is not True or memory.get("evidence_backed") is not True:
            raise ValueError("memory_not_reusable")
        if not isinstance(reuse_assessment, Mapping):
            raise ValueError("memory_reuse_assessment_required")
        if reuse_assessment.get("memory_digest") != memory.get("digest") or reuse_assessment.get("specification_digest") != specification.get("digest"):
            raise ValueError("memory_reuse_binding_mismatch")
        if reuse_assessment.get("planning_advisory") is not True:
            raise ValueError("memory_reuse_not_advisory")
        if reuse_assessment.get("freshness", {}).get("status") != "FRESH":
            raise ValueError("memory_freshness_not_verified")
        if not isinstance(memory_planning_projection, Mapping):
            raise ValueError("memory_planning_projection_required")
        if memory_planning_projection.get("schema") != "kemet.production.memory_planning_projection.v1":
            raise ValueError("memory_planning_projection_invalid")
        if memory_planning_projection.get("status") != "ACTIVE" or memory_planning_projection.get("planning_visible") is not True:
            raise ValueError("memory_planning_projection_inactive")
        if memory_planning_projection.get("memory_digest") != memory.get("digest"):
            raise ValueError("memory_planning_projection_binding_mismatch")
        if not memory_planning_projection.get("activation_record_digest"):
            raise ValueError("memory_activation_binding_missing")
        if not isinstance(memory_lifecycle_status, Mapping):
            raise ValueError("memory_lifecycle_status_required")
        if memory_lifecycle_status.get("schema") != "kemet.production.memory_lifecycle_status.v1":
            raise ValueError("memory_lifecycle_status_invalid")
        if memory_lifecycle_status.get("organization_id") != int(organization_id) or memory_lifecycle_status.get("project_id") != str(project_id):
            raise ValueError("memory_lifecycle_binding_mismatch")
        if memory_lifecycle_status.get("activation_record_digest") != memory_planning_projection.get("activation_record_digest"):
            raise ValueError("memory_lifecycle_activation_mismatch")
        if memory_lifecycle_status.get("status") != "ACTIVE" or memory_lifecycle_status.get("planning_visible") is not True:
            raise ValueError("memory_lifecycle_not_planning_visible")
        return self._finalize({"schema": "kemet.production.plan_context.v1", "version": 2, "organization_id": int(organization_id), "project_id": str(project_id), "specification_digest": str(specification.get("digest") or ""), "memory_digest": str(memory.get("digest") or ""), "memory_reuse_assessment_digest": str(reuse_assessment.get("digest") or ""), "memory_planning_projection_digest": str(memory_planning_projection.get("digest") or ""), "memory_lifecycle_status_digest": str(memory_lifecycle_status.get("digest") or ""), "memory_provenance": {"source_of_truth": memory.get("source_of_truth"), "evidence_digests": list(memory.get("evidence_digests") or [])}, "memory_freshness": dict(reuse_assessment.get("freshness") or {}), "memory_is_advisory": True, "canonical_state_mutation": False, "prompts_are_derived": True, "execution_authority": False, "external_execution": False, "authorization_issued": False, "execution_gate_bypass": False, "governance": self._governance()})

    def bind_critic_to_trajectory(self, *, organization_id: int, project_id: str, trajectory: Mapping[str, Any], critic: Mapping[str, Any]) -> dict[str, Any]:
        self._org(organization_id)
        self._mapping(trajectory, "trajectory")
        self._mapping(critic, "critic")
        if trajectory.get("organization_id") != int(organization_id) or critic.get("organization_id") != int(organization_id):
            raise ValueError("organization_mismatch")
        if trajectory.get("project_id") != str(project_id) or critic.get("project_id") != str(project_id):
            raise ValueError("project_mismatch")
        if str(critic.get("trajectory_digest") or "") != str(trajectory.get("digest") or ""):
            raise ValueError("trajectory_digest_mismatch")
        events = trajectory.get("events") or []
        target_id = str(critic.get("target_id") or "")
        bound = [dict(event) for event in events if str(event.get("node_id") or "") == target_id]
        if not bound:
            raise ValueError("critic_target_not_in_trajectory")
        return self._finalize({
            "schema": "kemet.production.critic_trajectory_binding.v1",
            "version": 1,
            "organization_id": int(organization_id),
            "project_id": str(project_id),
            "trajectory_digest": str(trajectory.get("digest") or ""),
            "critic_digest": str(critic.get("digest") or ""),
            "target_id": target_id,
            "matched_events": bound,
            "canonical_state_mutation": False,
            "learning_eligible": False,
            "governance": self._governance(),
        })

    def learning_eligibility(self, *, organization_id: int, project_id: str, critic: Mapping[str, Any], repair: Mapping[str, Any], replay_digest: str, paired_evaluation: Mapping[str, Any], binding_digest: str, evaluation_gate: Mapping[str, Any], verified_trace_gate: Mapping[str, Any] | None = None) -> dict[str, Any]:
        self._org(organization_id)
        for value, label in ((critic, "critic"), (repair, "repair"), (paired_evaluation, "paired_evaluation"), (evaluation_gate, "evaluation_gate")):
            self._mapping(value, label)
        if critic.get("organization_id") != int(organization_id) or repair.get("organization_id") != int(organization_id):
            raise ValueError("organization_mismatch")
        if critic.get("project_id") != str(project_id) or repair.get("project_id") != str(project_id):
            raise ValueError("project_mismatch")
        if not replay_digest or not binding_digest:
            raise ValueError("learning_evidence_required")
        if evaluation_gate.get("organization_id") != int(organization_id):
            raise ValueError("evaluation_gate_organization_mismatch")
        if evaluation_gate.get("project_id") != str(project_id):
            raise ValueError("evaluation_gate_project_mismatch")
        if evaluation_gate.get("schema") != "kemet.production.trajectory_evaluation_gate.v1":
            raise ValueError("evaluation_gate_schema_invalid")
        if evaluation_gate.get("learning_eligible") is not True:
            raise ValueError("evaluation_gate_not_eligible")
        if evaluation_gate.get("trajectory_digest") != str(critic.get("trajectory_digest") or ""):
            raise ValueError("evaluation_gate_trajectory_mismatch")
        if evaluation_gate.get("replay_digest") != str(replay_digest):
            raise ValueError("evaluation_gate_replay_mismatch")
        if evaluation_gate.get("paired_evaluation_digest") != str(paired_evaluation.get("digest") or ""):
            raise ValueError("evaluation_gate_pair_mismatch")
        repair_payload = repair.get("repair") if isinstance(repair.get("repair"), Mapping) else repair
        repaired = str(repair_payload.get("status") or "").lower() in {"verified", "passed", "completed"}
        eligible = repaired and str(repair.get("replay_digest") or replay_digest) == str(replay_digest)
        trace_verified = False
        trace_digest = ""
        if verified_trace_gate is not None:
            verified = production_learning_trace_gate.verify_learning_trace(organization_id=organization_id, project_id=project_id, gate_artifact=verified_trace_gate)
            trace_verified = bool(verified.get("verified"))
            trace_digest = str(verified.get("trace_digest") or "")
        if verified_trace_gate is not None and not trace_verified:
            raise ValueError("learning_trace_not_verified")
        if verified_trace_gate is not None:
            eligible = eligible and trace_verified
        return self._finalize({
            "schema": "kemet.production.learning_eligibility.v1",
            "version": 1,
            "organization_id": int(organization_id),
            "project_id": str(project_id),
            "critic_digest": str(critic.get("digest") or ""),
            "repair_digest": str(repair.get("digest") or ""),
            "trajectory_digest": str(critic.get("trajectory_digest") or ""),
            "trajectory_stage": str(critic.get("stage") or ""),
            "binding_digest": str(binding_digest),
            "evaluation_gate_digest": str(evaluation_gate.get("digest") or ""),
            "replay_digest": str(replay_digest),
            "paired_evaluation": dict(paired_evaluation),
            "repair_verified": repaired,
            "learning_eligible": eligible,
            "trace_verified": trace_verified,
            "trace_digest": trace_digest,
            "policy_deployment_allowed": False,
            "canonical_state_mutation": False,
            "human_approval_required": True,
            "governance": self._governance(),
        })


    def policy_proposal_from_verified_learning(self, *, organization_id: int, project_id: str, stage: str, patch: Mapping[str, Any], eligibility: Mapping[str, Any], verified_trace_gate: Mapping[str, Any]) -> dict[str, Any]:
        self._org(organization_id)
        self._mapping(eligibility, "eligibility")
        self._mapping(verified_trace_gate, "verified_trace_gate")
        if eligibility.get("organization_id") != int(organization_id) or eligibility.get("project_id") != str(project_id):
            raise ValueError("learning_trace_binding_mismatch")
        if eligibility.get("learning_eligible") is not True:
            raise ValueError("learning_not_eligible")
        verified = production_learning_trace_gate.verify_learning_trace(organization_id=organization_id, project_id=project_id, gate_artifact=verified_trace_gate)
        if verified["learning_eligible"] is not True:
            raise ValueError("learning_trace_not_eligible")
        if str(eligibility.get("digest") or "") not in [str(e.get("artifact_digest") or "") for e in (verified_trace_gate.get("trace") or {}).get("events", [])]:
            raise ValueError("learning_trace_eligibility_binding_invalid")
        proposal = self.policy_proposal_from_eligibility(organization_id=organization_id, project_id=project_id, stage=stage, patch=patch, eligibility=eligibility)
        proposal["learning_trace_digest"] = verified["trace_digest"]
        proposal["trace_verified"] = True
        proposal["digest"] = self._digest({k: v for k, v in proposal.items() if k != "digest"})
        return proposal

    def policy_proposal_from_eligibility(self, *, organization_id: int, project_id: str, stage: str, patch: Mapping[str, Any], eligibility: Mapping[str, Any]) -> dict[str, Any]:
        self._org(organization_id)
        self._mapping(eligibility, "eligibility")
        self._mapping(patch, "patch")
        if eligibility.get("organization_id") != int(organization_id):
            raise ValueError("organization_mismatch")
        if eligibility.get("project_id") != str(project_id):
            raise ValueError("project_mismatch")
        if eligibility.get("learning_eligible") is not True:
            raise ValueError("learning_not_eligible")
        if eligibility.get("policy_deployment_allowed") is not False:
            raise ValueError("policy_deployment_boundary_invalid")
        return self.propose_policy(
            organization_id=organization_id,
            project_id=project_id,
            stage=stage,
            patch=patch,
            trajectory_digest=str(eligibility.get("trajectory_digest") or ""),
            replay_digest=str(eligibility.get("replay_digest") or ""),
            paired_evaluation=dict(eligibility.get("paired_evaluation") or {}),
        )

    def build_policy_review_artifact(self, *, organization_id: int, project_id: str, proposal: Mapping[str, Any], learning_eligibility: Mapping[str, Any]) -> dict[str, Any]:
        self._org(organization_id)
        self._mapping(proposal, "proposal")
        self._mapping(learning_eligibility, "learning_eligibility")
        if proposal.get("organization_id") != int(organization_id) or learning_eligibility.get("organization_id") != int(organization_id):
            raise ValueError("organization_mismatch")
        if proposal.get("project_id") != str(project_id) or learning_eligibility.get("project_id") != str(project_id):
            raise ValueError("project_mismatch")
        if learning_eligibility.get("learning_eligible") is not True:
            raise ValueError("learning_not_eligible")
        if proposal.get("trace_verified") is True and not str(proposal.get("learning_trace_digest") or ""):
            raise ValueError("learning_trace_digest_required")
        if proposal.get("auto_deploy") is not False or proposal.get("canonical_state_mutation") is not False:
            raise ValueError("proposal_boundary_invalid")
        return self._finalize({
            "schema": "kemet.production.policy_review_artifact.v1",
            "version": 1,
            "organization_id": int(organization_id),
            "project_id": str(project_id),
            "proposal_digest": str(proposal.get("digest") or ""),
            "trajectory_digest": str(proposal.get("trajectory_digest") or ""),
            "trajectory_stage": str(proposal.get("stage") or ""),
            "learning_eligibility_digest": str(learning_eligibility.get("digest") or ""),
            "learning_trace_digest": str(proposal.get("learning_trace_digest") or ""),
            "trace_verified": proposal.get("trace_verified") is True,
            "stage": str(proposal.get("stage") or ""),
            "patch": dict(proposal.get("patch") or {}),
            "review_status": "PENDING_HUMAN_REVIEW",
            "decision_required_from_human": True,
            "approval_changes_status_only": True,
            "execution_authority": False,
            "external_execution": False,
            "execution_gate_bypass": False,
            "auto_deploy": False,
            "canonical_state_mutation": False,
            "governance": self._governance(),
        })

    def record_policy_review_decision(self, *, organization_id: int, project_id: str, review_artifact: Mapping[str, Any], decision: str, approver_id: int) -> dict[str, Any]:
        self._org(organization_id)
        self._mapping(review_artifact, "review_artifact")
        if review_artifact.get("organization_id") != int(organization_id) or review_artifact.get("project_id") != str(project_id):
            raise ValueError("review_tenant_mismatch")
        if str(review_artifact.get("review_status") or "") != "PENDING_HUMAN_REVIEW":
            raise ValueError("review_not_pending")
        if int(approver_id or 0) <= 0:
            raise ValueError("approver_required")
        normalized = str(decision or "").upper()
        if normalized not in {"APPROVED", "REJECTED"}:
            raise ValueError("review_decision_invalid")
        return self._finalize({
            "schema": "kemet.production.policy_review_decision.v1",
            "version": 1,
            "organization_id": int(organization_id),
            "project_id": str(project_id),
            "review_artifact_digest": str(review_artifact.get("digest") or ""),
            "proposal_digest": str(review_artifact.get("proposal_digest") or ""),
            "trajectory_digest": str(review_artifact.get("trajectory_digest") or ""),
            "trajectory_stage": str(review_artifact.get("trajectory_stage") or ""),
            "learning_trace_digest": str(review_artifact.get("learning_trace_digest") or ""),
            "trace_verified": review_artifact.get("trace_verified") is True,
            "decision": normalized,
            "approver_id": int(approver_id),
            "status": f"REVIEW_{normalized}",
            "execution_authority": False,
            "external_execution": False,
            "execution_gate_bypass": False,
            "authorization_issued": False,
            "canonical_state_mutation": False,
            "governance": self._governance(),
        })

    def record_policy_impact(self, *, organization_id: int, project_id: str, review_decision: Mapping[str, Any], replay_digest: str, post_replay_evaluation: Mapping[str, Any], evaluation_gate: Mapping[str, Any]) -> dict[str, Any]:
        self._org(organization_id)
        self._mapping(review_decision, "review_decision")
        self._mapping(post_replay_evaluation, "post_replay_evaluation")
        self._mapping(evaluation_gate, "evaluation_gate")
        if review_decision.get("organization_id") != int(organization_id) or review_decision.get("project_id") != str(project_id):
            raise ValueError("review_tenant_mismatch")
        if str(review_decision.get("decision") or "") != "APPROVED":
            raise ValueError("review_not_approved")
        if not replay_digest:
            raise ValueError("replay_digest_required")
        if post_replay_evaluation.get("valid") is not True:
            raise ValueError("post_replay_evaluation_invalid")
        if evaluation_gate.get("schema") != "kemet.production.trajectory_evaluation_gate.v1":
            raise ValueError("evaluation_gate_schema_invalid")
        if evaluation_gate.get("organization_id") != int(organization_id) or evaluation_gate.get("project_id") != str(project_id):
            raise ValueError("evaluation_gate_tenant_mismatch")
        if evaluation_gate.get("trajectory_digest") != str(review_decision.get("trajectory_digest") or ""):
            raise ValueError("evaluation_gate_trajectory_mismatch")
        if evaluation_gate.get("replay_digest") != str(replay_digest):
            raise ValueError("evaluation_gate_replay_mismatch")
        if evaluation_gate.get("learning_eligible") is not True or evaluation_gate.get("quality_verified") is not True:
            raise ValueError("evaluation_gate_not_qualified")
        if review_decision.get("trace_verified") is True and not str(review_decision.get("learning_trace_digest") or ""):
            raise ValueError("learning_trace_digest_required")
        if evaluation_gate.get("freshness", {}).get("status") != "FRESH":
            raise ValueError("evaluation_gate_stale")
        if evaluation_gate.get("policy_deployment_allowed") is not False or evaluation_gate.get("canonical_state_mutation") is not False:
            raise ValueError("evaluation_gate_boundary_invalid")
        return self._finalize({
            "schema": "kemet.production.policy_impact_evidence.v1",
            "version": 1,
            "organization_id": int(organization_id),
            "project_id": str(project_id),
            "review_decision_digest": str(review_decision.get("digest") or ""),
            "proposal_digest": str(review_decision.get("proposal_digest") or ""),
            "trajectory_digest": str(review_decision.get("trajectory_digest") or ""),
            "trajectory_stage": str(review_decision.get("trajectory_stage") or ""),
            "replay_digest": str(replay_digest),
            "evaluation_gate_digest": str(evaluation_gate.get("digest") or ""),
            "learning_trace_digest": str(review_decision.get("learning_trace_digest") or ""),
            "trace_verified": review_decision.get("trace_verified") is True,
            "post_replay_evaluation": dict(post_replay_evaluation),
            "measured": True,
            "learning_reusable": True,
            "canonical_state_mutation": False,
            "policy_deployment_allowed": False,
            "execution_authority": False,
            "external_execution": False,
            "human_approval_required": True,
            "governance": self._governance(),
        })

    def memory_from_verified_policy_impact(self, *, organization_id: int, project_id: str, impact: Mapping[str, Any], verified_trace_gate: Mapping[str, Any], facts: list[Mapping[str, Any]] | None = None, invariants: list[Mapping[str, Any]] | None = None, failure_patterns: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        self._org(organization_id)
        self._mapping(impact, "policy_impact")
        self._mapping(verified_trace_gate, "verified_trace_gate")
        verified = production_learning_trace_gate.verify_learning_trace(organization_id=organization_id, project_id=project_id, gate_artifact=verified_trace_gate)
        if impact.get("organization_id") != int(organization_id) or impact.get("project_id") != str(project_id):
            raise ValueError("impact_trace_binding_mismatch")
        if impact.get("digest") not in [str(e.get("artifact_digest") or "") for e in (verified_trace_gate.get("trace") or {}).get("events", [])]:
            raise ValueError("impact_trace_binding_invalid")
        memory = self.memory_from_policy_impact(organization_id=organization_id, project_id=project_id, impact=impact, facts=facts, invariants=invariants, failure_patterns=failure_patterns)
        memory["learning_trace_digest"] = verified["trace_digest"]
        memory["trace_verified"] = True
        memory["digest"] = self._digest({k: v for k, v in memory.items() if k != "digest"})
        return memory

    def memory_from_policy_impact(self, *, organization_id: int, project_id: str, impact: Mapping[str, Any], facts: list[Mapping[str, Any]] | None = None, invariants: list[Mapping[str, Any]] | None = None, failure_patterns: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
        self._org(organization_id)
        self._mapping(impact, "policy_impact")
        if impact.get("organization_id") != int(organization_id) or impact.get("project_id") != str(project_id):
            raise ValueError("organization_mismatch")
        if impact.get("measured") is not True or impact.get("learning_reusable") is not True:
            raise ValueError("measured_learning_required")
        evaluation_gate_digest = str(impact.get("evaluation_gate_digest") or "")
        if not evaluation_gate_digest:
            raise ValueError("evaluation_gate_provenance_required")
        if impact.get("policy_deployment_allowed") is not False or impact.get("canonical_state_mutation") is not False:
            raise ValueError("impact_boundary_invalid")
        evidence = [str(impact.get("digest") or ""), str(impact.get("replay_digest") or ""), evaluation_gate_digest]
        lineage = self.memory_lineage(
            organization_id=organization_id, project_id=project_id,
            impact_digest=str(impact.get("digest") or ""),
            evaluation_gate_digest=evaluation_gate_digest,
            trajectory_digest=str(impact.get("trajectory_digest") or ""),
            replay_digest=str(impact.get("replay_digest") or ""),
            evidence_digests=evidence,
            freshness=impact.get("freshness") if isinstance(impact.get("freshness"), Mapping) else {"status": "FRESH", "verified_at": "derived-from-gated-impact"},
        )
        memory = self.memory(
            organization_id=organization_id,
            project_id=project_id,
            facts=list(facts or []),
            invariants=list(invariants or []),
            failure_patterns=list(failure_patterns or []),
            evidence_digests=[x for x in evidence if x],
        )
        memory["lineage_digest"] = lineage["digest"]
        memory["lineage"] = lineage
        memory["digest"] = self._digest({k: v for k, v in memory.items() if k != "digest"})
        return memory

    def bind_policy_impact_to_graph(self, *, organization_id: int, project_id: str, impact: Mapping[str, Any], trajectory: Mapping[str, Any], memory: Mapping[str, Any], stage: str, evidence_digests: list[str], confidence: float, min_confidence: float = 0.80, min_evidence: int = 2) -> dict[str, Any]:
        self._org(organization_id)
        for value, label in ((impact, "impact"), (trajectory, "trajectory"), (memory, "memory")):
            self._mapping(value, label)
        if impact.get("organization_id") != int(organization_id) or trajectory.get("organization_id") != int(organization_id) or memory.get("organization_id") != int(organization_id):
            raise ValueError("organization_mismatch")
        if impact.get("project_id") != str(project_id) or trajectory.get("project_id") != str(project_id) or memory.get("project_id") != str(project_id):
            raise ValueError("project_mismatch")
        trajectory_digest = str(trajectory.get("digest") or "")
        if not trajectory_digest or str(impact.get("trajectory_digest") or "") != trajectory_digest:
            raise ValueError("trajectory_binding_mismatch")
        stage = str(stage or "")
        events = trajectory.get("events") if isinstance(trajectory.get("events"), list) else []
        matched = [event for event in events if isinstance(event, Mapping) and str(event.get("node_id") or "") == stage]
        if not matched:
            raise ValueError("trajectory_stage_not_found")
        normalized_evidence = sorted({str(item) for item in evidence_digests if str(item)})
        if len(normalized_evidence) < int(min_evidence):
            raise ValueError("evidence_threshold_not_met")
        confidence_value = float(confidence)
        if not 0.0 <= confidence_value <= 1.0 or confidence_value < float(min_confidence):
            raise ValueError("confidence_threshold_not_met")
        memory_digest = str(memory.get("digest") or "")
        if not memory_digest:
            raise ValueError("memory_digest_required")
        return self._finalize({
            "schema": "kemet.production.policy_impact_graph_binding.v1",
            "version": 1,
            "organization_id": int(organization_id),
            "project_id": str(project_id),
            "impact_digest": str(impact.get("digest") or ""),
            "trajectory_digest": trajectory_digest,
            "trajectory_stage": stage,
            "matched_events": matched,
            "memory_digest": memory_digest,
            "evidence_digests": normalized_evidence,
            "confidence": confidence_value,
            "thresholds": {"min_confidence": float(min_confidence), "min_evidence": int(min_evidence)},
            "reuse_eligible": True,
            "canonical_state_mutation": False,
            "execution_authority": False,
            "external_execution": False,
            "policy_deployment_allowed": False,
            "governance": self._governance(),
        })

    def assess_memory_reuse(self, *, organization_id: int, project_id: str, memory: Mapping[str, Any], binding: Mapping[str, Any], specification: Mapping[str, Any], freshness: Mapping[str, Any]) -> dict[str, Any]:
        self._org(organization_id)
        for value, label in ((memory, "memory"), (binding, "binding"), (specification, "specification"), (freshness, "freshness")):
            self._mapping(value, label)
        if memory.get("organization_id") != int(organization_id) or binding.get("organization_id") != int(organization_id) or specification.get("organization_id") != int(organization_id):
            raise ValueError("organization_mismatch")
        if memory.get("project_id") != str(project_id) or binding.get("project_id") != str(project_id) or specification.get("project_id") != str(project_id):
            raise ValueError("project_mismatch")
        if binding.get("reuse_eligible") is not True or binding.get("memory_digest") != memory.get("digest"):
            raise ValueError("memory_reuse_not_eligible")
        evidence = {str(item) for item in (memory.get("evidence_digests") or []) if str(item)}
        impact_digest = str(binding.get("impact_digest") or "")
        if not impact_digest or impact_digest not in evidence:
            raise ValueError("memory_impact_provenance_missing")
        lineage = memory.get("lineage") if isinstance(memory.get("lineage"), Mapping) else None
        if not lineage or lineage.get("schema") != self.SCHEMAS["memory_lineage"]:
            raise ValueError("memory_lineage_required")
        if lineage.get("digest") != memory.get("lineage_digest"):
            raise ValueError("memory_lineage_digest_mismatch")
        if lineage.get("impact_digest") != impact_digest or lineage.get("trajectory_digest") != binding.get("trajectory_digest"):
            raise ValueError("memory_lineage_binding_mismatch")
        if len(evidence) < 3:
            raise ValueError("memory_evidence_lineage_incomplete")
        if freshness.get("status") != "FRESH" or not freshness.get("verified_at"):
            raise ValueError("memory_freshness_not_verified")
        return self._finalize({
            "schema": "kemet.production.memory_reuse_assessment.v1",
            "version": 1,
            "organization_id": int(organization_id),
            "project_id": str(project_id),
            "memory_digest": str(memory.get("digest") or ""),
            "binding_digest": str(binding.get("digest") or ""),
            "specification_digest": str(specification.get("digest") or ""),
            "freshness": dict(freshness),
            "provenance": {"source_of_truth": memory.get("source_of_truth"), "evidence_digests": list(memory.get("evidence_digests") or [])},
            "planning_advisory": True,
            "execution_authority": False,
            "external_execution": False,
            "authorization_issued": False,
            "execution_gate_bypass": False,
            "canonical_state_mutation": False,
            "policy_deployment_allowed": False,
            "governance": self._governance(),
        })

production_intelligence = ProductionIntelligence()
