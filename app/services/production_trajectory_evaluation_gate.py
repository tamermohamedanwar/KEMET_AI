"""Deterministic evaluation contracts for Production Intelligence learning gates.
This service validates replay lineage and evaluation evidence without executing work.
"""
from __future__ import annotations
from hashlib import sha256
import json
from typing import Any, Mapping


class ProductionTrajectoryEvaluationGate:
    VERSION = "1.0"
    SCHEMA = "kemet.production.trajectory_evaluation_gate.v1"
    REPLAY_SCHEMA = "kemet.production.replay_evidence.v1"
    PAIRED_SCHEMA = "kemet.production.paired_evaluation.v1"

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

    def replay_evidence(self, *, organization_id: int, project_id: str,
                        trajectory: Mapping[str, Any], replay_digest: str,
                        replay_status: str, output_digest: str,
                        evidence_digests: list[str]) -> dict[str, Any]:
        self._mapping(trajectory, "trajectory")
        if int(organization_id or 0) <= 0 or not project_id:
            raise ValueError("trajectory_binding_required")
        if trajectory.get("organization_id") != int(organization_id):
            raise ValueError("organization_mismatch")
        if trajectory.get("project_id") != str(project_id):
            raise ValueError("project_mismatch")
        if not replay_digest or not output_digest:
            raise ValueError("replay_evidence_required")
        if str(replay_status).upper() != "VERIFIED":
            raise ValueError("replay_not_verified")
        evidence = sorted({str(x) for x in evidence_digests if str(x)})
        if not evidence:
            raise ValueError("replay_evidence_required")
        return self._finalize({
            "schema": self.REPLAY_SCHEMA, "version": 1,
            "organization_id": int(organization_id), "project_id": str(project_id),
            "trajectory_digest": str(trajectory.get("digest") or ""),
            "replay_digest": str(replay_digest), "replay_status": "VERIFIED",
            "output_digest": str(output_digest), "evidence_digests": evidence,
            "replay_lineage_verified": True, "canonical_state_mutation": False,
            "governance": self._governance(),
        })

    def paired_evaluation(self, *, organization_id: int, project_id: str,
                          trajectory_digest: str, replay: Mapping[str, Any],
                          baseline_digest: str, candidate_digest: str,
                          valid: bool, metrics: Mapping[str, Any],
                          confidence: float, evidence_digests: list[str]) -> dict[str, Any]:
        self._mapping(replay, "replay")
        self._mapping(metrics, "metrics")
        if replay.get("organization_id") != int(organization_id):
            raise ValueError("organization_mismatch")
        if replay.get("project_id") != str(project_id):
            raise ValueError("project_mismatch")
        if replay.get("trajectory_digest") != str(trajectory_digest):
            raise ValueError("trajectory_digest_mismatch")
        if replay.get("replay_status") != "VERIFIED":
            raise ValueError("replay_not_verified")
        if not baseline_digest or not candidate_digest:
            raise ValueError("paired_artifacts_required")
        score = float(confidence)
        if not 0.0 <= score <= 1.0:
            raise ValueError("confidence_out_of_range")
        evidence = sorted({str(x) for x in evidence_digests if str(x)})
        if not evidence:
            raise ValueError("paired_evaluation_evidence_required")
        if valid is not True:
            raise ValueError("paired_evaluation_invalid")
        return self._finalize({
            "schema": self.PAIRED_SCHEMA, "version": 1,
            "organization_id": int(organization_id), "project_id": str(project_id),
            "trajectory_digest": str(trajectory_digest),
            "replay_digest": str(replay.get("replay_digest") or ""),
            "baseline_digest": str(baseline_digest), "candidate_digest": str(candidate_digest),
            "valid": True, "metrics": dict(metrics), "confidence": score,
            "evidence_digests": evidence, "quality_verified": True,
            "canonical_state_mutation": False, "policy_deployment_allowed": False,
            "governance": self._governance(),
        })

    def evaluate(self, *, organization_id: int, project_id: str,
                 trajectory: Mapping[str, Any], replay: Mapping[str, Any],
                 paired: Mapping[str, Any], freshness: Mapping[str, Any],
                 min_confidence: float = 0.80, min_evidence: int = 2) -> dict[str, Any]:
        for value, label in ((trajectory, "trajectory"), (replay, "replay"),
                             (paired, "paired"), (freshness, "freshness")):
            self._mapping(value, label)
        if trajectory.get("organization_id") != int(organization_id) or replay.get("organization_id") != int(organization_id) or paired.get("organization_id") != int(organization_id):
            raise ValueError("organization_mismatch")
        if trajectory.get("project_id") != str(project_id) or replay.get("project_id") != str(project_id) or paired.get("project_id") != str(project_id):
            raise ValueError("project_mismatch")
        if replay.get("trajectory_digest") != trajectory.get("digest") or paired.get("trajectory_digest") != trajectory.get("digest"):
            raise ValueError("trajectory_lineage_mismatch")
        if paired.get("replay_digest") != replay.get("replay_digest"):
            raise ValueError("replay_lineage_mismatch")
        if paired.get("valid") is not True or paired.get("quality_verified") is not True:
            raise ValueError("paired_evaluation_invalid")
        if freshness.get("status") != "FRESH" or not freshness.get("verified_at"):
            raise ValueError("evaluation_freshness_not_verified")
        confidence = float(paired.get("confidence") or 0.0)
        evidence = sorted({str(x) for x in list(replay.get("evidence_digests") or []) + list(paired.get("evidence_digests") or []) if str(x)})
        if confidence < float(min_confidence):
            raise ValueError("evaluation_confidence_threshold_not_met")
        if len(evidence) < int(min_evidence):
            raise ValueError("evaluation_evidence_threshold_not_met")
        return self._finalize({
            "schema": self.SCHEMA, "version": 1,
            "organization_id": int(organization_id), "project_id": str(project_id),
            "trajectory_digest": str(trajectory.get("digest") or ""),
            "replay_digest": str(replay.get("replay_digest") or ""),
            "paired_evaluation_digest": str(paired.get("digest") or ""),
            "freshness": dict(freshness), "confidence": confidence,
            "evidence_digests": evidence,
            "quality_verified": True, "learning_eligible": True,
            "policy_deployment_allowed": False, "canonical_state_mutation": False,
            "execution_authority": False, "external_execution": False,
            "governance": self._governance(),
        })


production_trajectory_evaluation_gate = ProductionTrajectoryEvaluationGate()
