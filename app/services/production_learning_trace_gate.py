"""Trace-integrated learning gate for the canonical Production Intelligence loop."""
from __future__ import annotations

from typing import Any, Mapping

from app.services.production_trace_integrity import production_trace_integrity


class ProductionLearningTraceGate:
    SCHEMA = "kemet.production.learning_trace_gate.v1"

    @staticmethod
    def _mapping(value: Any, label: str) -> None:
        if not isinstance(value, Mapping):
            raise ValueError(f"{label}_mapping_required")

    @classmethod
    def _event(cls, stage: str, artifact: Mapping[str, Any], *, evidence: list[str] | None = None,
               decision: str = "", approval_digest: str = "") -> dict[str, Any]:
        return {
            "stage": stage,
            "artifact_digest": str(artifact.get("digest") or ""),
            "evidence_digests": list(evidence or []),
            "decision": decision,
            "actor_type": "system",
            "policy_version": "production-intelligence-v1",
            "approval_digest": approval_digest,
        }

    @classmethod
    def build_learning_trace(cls, *, organization_id: int, project_id: str,
                             correlation_id: str, trajectory: Mapping[str, Any],
                             critic: Mapping[str, Any], repair: Mapping[str, Any],
                             replay: Mapping[str, Any], paired_evaluation: Mapping[str, Any],
                             evaluation_gate: Mapping[str, Any], review_decision: Mapping[str, Any],
                             impact: Mapping[str, Any], eligibility: Mapping[str, Any],
                             memory: Mapping[str, Any] | None = None) -> dict[str, Any]:
        artifacts = {
            "trajectory": trajectory, "critic": critic, "repair": repair,
            "replay": replay, "paired": paired_evaluation,
            "evaluation": evaluation_gate, "review": review_decision,
            "impact": impact, "eligibility": eligibility,
        }
        for label, value in artifacts.items():
            cls._mapping(value, label)
        if memory is not None:
            cls._mapping(memory, "memory")
        for label, value in artifacts.items():
            if value.get("organization_id") != int(organization_id):
                raise ValueError(f"{label}_organization_mismatch")
            if value.get("project_id") != str(project_id):
                raise ValueError(f"{label}_project_mismatch")

        trajectory_digest = str(trajectory.get("digest") or "")
        if not trajectory_digest:
            raise ValueError("trajectory_digest_required")
        if critic.get("trajectory_digest") != trajectory_digest:
            raise ValueError("critic_trajectory_mismatch")
        if evaluation_gate.get("trajectory_digest") != trajectory_digest:
            raise ValueError("evaluation_trajectory_mismatch")
        if review_decision.get("trajectory_digest") != trajectory_digest:
            raise ValueError("review_trajectory_mismatch")
        if impact.get("trajectory_digest") != trajectory_digest:
            raise ValueError("impact_trajectory_mismatch")
        if eligibility.get("trajectory_digest") != trajectory_digest:
            raise ValueError("eligibility_trajectory_mismatch")
        if replay.get("replay_digest") != eligibility.get("replay_digest"):
            raise ValueError("replay_binding_mismatch")
        if evaluation_gate.get("replay_digest") != replay.get("replay_digest"):
            raise ValueError("evaluation_replay_mismatch")
        if evaluation_gate.get("paired_evaluation_digest") != paired_evaluation.get("digest"):
            raise ValueError("paired_evaluation_binding_mismatch")
        if review_decision.get("decision") != "APPROVED":
            raise ValueError("policy_review_not_approved")
        if impact.get("review_decision_digest") != review_decision.get("digest"):
            raise ValueError("impact_review_binding_mismatch")
        if impact.get("evaluation_gate_digest") != evaluation_gate.get("digest"):
            raise ValueError("impact_evaluation_binding_mismatch")
        if eligibility.get("evaluation_gate_digest") != evaluation_gate.get("digest"):
            raise ValueError("eligibility_evaluation_binding_mismatch")
        if eligibility.get("learning_eligible") is not True:
            raise ValueError("learning_not_eligible")

        evidence = sorted({
            str(x) for x in (
                list(critic.get("evidence_digests") or [])
                + list(replay.get("evidence_digests") or [])
                + list(paired_evaluation.get("evidence_digests") or [])
                + list(impact.get("post_replay_evaluation", {}).get("evidence_digests", []))
            ) if str(x)
        })
        if len(evidence) < 2:
            raise ValueError("learning_trace_evidence_incomplete")

        events = [
            cls._event("PLAN", trajectory, evidence=[trajectory_digest]),
            cls._event("EVIDENCE", critic, evidence=list(critic.get("evidence_digests") or [])),
            cls._event("EVALUATION", evaluation_gate, evidence=[str(evaluation_gate.get("digest") or "")]),
            cls._event("QA", critic, evidence=list(critic.get("evidence_digests") or [])),
            cls._event("REPAIR", repair, evidence=[str(repair.get("digest") or "")]),
            cls._event("REPLAY", replay, evidence=list(replay.get("evidence_digests") or [])),
            cls._event("PAIRED_EVALUATION", paired_evaluation, evidence=list(paired_evaluation.get("evidence_digests") or [])),
            cls._event("POLICY_REVIEW", review_decision, evidence=[str(review_decision.get("review_artifact_digest") or "")], decision="APPROVED", approval_digest=str(review_decision.get("digest") or "")),
            cls._event("IMPACT", impact, evidence=[str(impact.get("evaluation_gate_digest") or ""), str(impact.get("replay_digest") or "")]),
            cls._event("LEARNING", eligibility, evidence=[str(eligibility.get("digest") or ""), str(impact.get("digest") or "")]),
        ]
        source = [str(value.get("digest") or "") for value in artifacts.values() if value.get("digest")]
        if memory is not None and memory.get("digest"):
            source.append(str(memory["digest"]))
        trace = production_trace_integrity.build(
            organization_id=organization_id, project_id=project_id,
            correlation_id=correlation_id, events=events, source_digests=source,
        )
        return {
            "schema": cls.SCHEMA,
            "version": 1,
            "organization_id": int(organization_id),
            "project_id": str(project_id),
            "correlation_id": str(correlation_id),
            "trace": trace,
            "trace_digest": trace["digest"],
            "learning_eligible": True,
            "memory_digest": str(memory.get("digest") or "") if memory else "",
            "canonical_state_mutation": False,
            "execution_authority": False,
            "external_execution": False,
            "policy_deployment_allowed": False,
            "human_approval_required": True,
            "mcp": False,
        }

    @classmethod
    def verify_learning_trace(cls, *, organization_id: int, project_id: str,
                              gate_artifact: Mapping[str, Any]) -> dict[str, Any]:
        cls._mapping(gate_artifact, "gate_artifact")
        if gate_artifact.get("schema") != cls.SCHEMA:
            raise ValueError("learning_trace_gate_schema_invalid")
        if gate_artifact.get("organization_id") != int(organization_id):
            raise ValueError("learning_trace_gate_organization_mismatch")
        if gate_artifact.get("project_id") != str(project_id):
            raise ValueError("learning_trace_gate_project_mismatch")
        if gate_artifact.get("learning_eligible") is not True:
            raise ValueError("learning_trace_gate_not_eligible")
        verified = production_trace_integrity.verify(gate_artifact.get("trace") or {})
        if verified["digest"] != gate_artifact.get("trace_digest"):
            raise ValueError("learning_trace_gate_digest_mismatch")
        if gate_artifact.get("canonical_state_mutation") is not False or gate_artifact.get("execution_authority") is not False:
            raise ValueError("learning_trace_gate_boundary_invalid")
        return {"verified": True, "trace_digest": verified["digest"], "event_count": verified["event_count"], "learning_eligible": True}


production_learning_trace_gate = ProductionLearningTraceGate()
