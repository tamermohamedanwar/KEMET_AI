from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping


class MiroFishSimulationService:
    VERSION = "1.0"
    SCHEMA = "kemet.mirofish.simulation.v1"
    LICENSE = "AGPL-3.0"

    def build_simulation_request(self, *, organization_id: int, content_id: str,
                                 seed_digest: str, question: str,
                                 scenarios: list[str] | None = None) -> dict[str, Any]:
        if int(organization_id or 0) <= 0:
            raise ValueError("organization_required")
        if not self._sha256(seed_digest):
            raise ValueError("seed_digest_required")
        if not str(content_id or "").strip():
            raise ValueError("content_id_required")
        if not str(question or "").strip():
            raise ValueError("simulation_question_required")
        selected = [str(x).strip() for x in (scenarios or ["audience_reaction", "story_hook", "cta_conversion"]) if str(x).strip()]
        if not selected:
            raise ValueError("scenario_required")
        payload = {
            "schema": self.SCHEMA, "version": self.VERSION,
            "organization_id": int(organization_id), "content_id": str(content_id),
            "seed_digest": str(seed_digest).lower(),
            "question": str(question)[:2000], "scenarios": selected,
            "adapter": {"provider": "mirofish", "boundary": "external_governed_adapter",
                        "execution_authority": False, "decision_authority": False},
            "simulation": {"status": "REQUESTED", "external_execution": False,
                           "max_rounds": 10, "cost_control_required": True},
            "evidence": {"status": "not_observed", "confidence": None,
                         "must_not_be_presented_as_fact": True},
            "license": self.LICENSE,
            "governance": {"read_only": True, "human_approval_required": True,
                           "canonical_executor": "kemet_canonical_runtime"},
        }
        payload["request_digest"] = self._digest(payload)
        return payload

    def record_simulation_evidence(self, *, request: Mapping[str, Any],
                                   report_digest: str, findings: list[Mapping[str, Any]],
                                   confidence: float | None = None) -> dict[str, Any]:
        if not isinstance(request, Mapping) or not request.get("request_digest"):
            raise ValueError("simulation_request_required")
        if not self._sha256(report_digest):
            raise ValueError("report_digest_required")
        if not isinstance(findings, list) or not findings:
            raise ValueError("findings_required")
        if confidence is not None and not 0 <= float(confidence) <= 1:
            raise ValueError("confidence_out_of_range")
        evidence = {
            "schema": "kemet.mirofish.simulation_evidence.v1",
            "request_digest": str(request["request_digest"]),
            "report_digest": str(report_digest).lower(),
            "findings": [dict(item) for item in findings],
            "confidence": confidence,
            "status": "observed_simulation_evidence",
            "interpretation": "scenario_evidence_for_human_review",
            "not_a_fact": True, "not_a_prediction_guarantee": True,
            "execution_authority": False, "auto_publish": False,
            "human_review_required": True,
        }
        evidence["evidence_digest"] = self._digest(evidence)
        return evidence

    @staticmethod
    def _sha256(value: Any) -> bool:
        text = str(value or "").strip().lower()
        if len(text) != 64:
            return False
        try:
            int(text, 16)
        except ValueError:
            return False
        return True

    @staticmethod
    def _digest(payload: Mapping[str, Any]) -> str:
        raw = json.dumps(dict(payload), sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode()).hexdigest()


mirofish_simulation_service = MiroFishSimulationService()
