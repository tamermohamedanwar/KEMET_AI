"""Deterministic critic and repair evidence contracts for Production Intelligence.
This service records evidence and bounded repair linkage; it never executes repairs.
"""
from __future__ import annotations
from hashlib import sha256
import json
from typing import Any, Mapping


class ProductionCriticEvidence:
    VERSION = "1.0"
    SCHEMA = "kemet.production.critic_evidence.v1"
    REPAIR_SCHEMA = "kemet.production.repair_evidence.v1"

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
            "canonical_state_mutation": False,
        }

    def critic_evidence(
        self, *, organization_id: int, project_id: str, stage: str,
        target_id: str, trajectory_digest: str, qa_evidence: Mapping[str, Any],
        observed: Mapping[str, Any], expected: Mapping[str, Any],
        category: str, severity: str, finding: str,
        evidence_digests: list[str], repair_recommendation: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._org(organization_id)
        if not project_id or not stage or not target_id or not trajectory_digest:
            raise ValueError("critic_binding_required")
        self._mapping(qa_evidence, "qa_evidence")
        self._mapping(observed, "observed")
        self._mapping(expected, "expected")
        if not category or not severity or not finding:
            raise ValueError("critic_finding_required")
        if not isinstance(evidence_digests, list) or not evidence_digests:
            raise ValueError("critic_evidence_required")
        if not all(str(x).strip() for x in evidence_digests):
            raise ValueError("critic_evidence_digest_required")
        recommendation = dict(repair_recommendation or {})
        return self._finalize({
            "schema": self.SCHEMA, "version": 1,
            "organization_id": int(organization_id), "project_id": str(project_id),
            "stage": str(stage), "target_id": str(target_id),
            "trajectory_digest": str(trajectory_digest),
            "qa_evidence": dict(qa_evidence),
            "observed": dict(observed), "expected": dict(expected),
            "category": str(category), "severity": str(severity),
            "finding": str(finding),
            "evidence_digests": [str(x) for x in evidence_digests],
            "repair_recommendation": recommendation,
            "repair_bounded": bool(recommendation) and bool(recommendation.get("stage_local", True)),
            "learning_eligible": False,
            "governance": self._governance(),
        })

    def repair_evidence(
        self, *, organization_id: int, project_id: str, critic: Mapping[str, Any],
        repair: Mapping[str, Any], replay_digest: str | None = None,
        paired_evaluation: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        self._org(organization_id)
        self._mapping(critic, "critic")
        self._mapping(repair, "repair")
        if critic.get("organization_id") != int(organization_id):
            raise ValueError("organization_mismatch")
        if critic.get("project_id") != str(project_id):
            raise ValueError("project_mismatch")
        if critic.get("schema") != self.SCHEMA:
            raise ValueError("critic_schema_required")
        if not replay_digest:
            learning_eligible = False
        else:
            self._mapping(paired_evaluation or {}, "paired_evaluation")
            learning_eligible = bool((paired_evaluation or {}).get("valid"))
        return self._finalize({
            "schema": self.REPAIR_SCHEMA, "version": 1,
            "organization_id": int(organization_id), "project_id": str(project_id),
            "critic_digest": str(critic.get("digest") or ""),
            "target_id": str(critic.get("target_id") or ""),
            "stage": str(critic.get("stage") or ""),
            "repair": dict(repair),
            "replay_digest": str(replay_digest or ""),
            "paired_evaluation": dict(paired_evaluation or {}),
            "repair_executed_by_contract": False,
            "learning_eligible": learning_eligible,
            "policy_deployment_allowed": False,
            "governance": self._governance(),
        })


production_critic_evidence = ProductionCriticEvidence()

