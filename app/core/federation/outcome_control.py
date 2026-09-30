from __future__ import annotations

from hashlib import sha256
import json
from typing import Any


class OutcomeControlError(ValueError):
    pass


class OutcomeControlService:
    VERSION = "1.0"

    @staticmethod
    def _digest(value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return sha256(raw.encode("utf-8")).hexdigest()

    def contract(self, *, decision: dict[str, Any], expected_metrics: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if not isinstance(decision, dict) or not decision.get("decision_id"):
            raise OutcomeControlError("decision_id_required")
        metrics = []
        for item in expected_metrics or []:
            if not isinstance(item, dict) or not item.get("metric"):
                continue
            metrics.append({
                "metric": str(item["metric"]),
                "baseline": item.get("baseline"),
                "target": item.get("target"),
                "unit": str(item.get("unit") or ""),
                "direction": str(item.get("direction") or "increase"),
            })
        payload = {
            "version": self.VERSION,
            "type": "governed_outcome_contract",
            "decision_id": str(decision["decision_id"]),
            "task_id": str(decision.get("task_id") or ""),
            "organization_id": int(decision.get("organization_id") or 0),
            "decision_digest": str(decision.get("digest") or ""),
            "decision_hash": str(decision.get("decision_hash") or decision.get("digest") or ""),
            "expected_metrics": metrics,
            "measurement_policy": "observational_only",
            "human_review_required": True,
            "auto_execute": False,
            "governance": {"read_only": True, "external_execution": False, "database_mutation": False, "causal_claim": False},
        }
        payload["digest"] = self._digest(payload)
        return payload

    def _validate_contract(self, contract: dict[str, Any]) -> None:
        if not isinstance(contract, dict) or not contract.get("digest"):
            raise OutcomeControlError("outcome_contract_required")
        supplied = str(contract["digest"])
        payload = dict(contract)
        payload.pop("digest", None)
        if supplied != self._digest(payload):
            raise OutcomeControlError("outcome_contract_integrity_mismatch")
        if not contract.get("decision_id") or not contract.get("organization_id") or not contract.get("decision_hash"):
            raise OutcomeControlError("outcome_contract_identity_required")
        if contract.get("auto_execute") is not False:
            raise OutcomeControlError("outcome_contract_execution_forbidden")

    def measure(self, contract: dict[str, Any], observed: dict[str, Any]) -> dict[str, Any]:
        self._validate_contract(contract)
        if not isinstance(observed, dict):
            raise OutcomeControlError("observed_metrics_required")
        observed_org = observed.get("organization_id")
        if observed_org is not None and int(observed_org) != int(contract["organization_id"]):
            raise OutcomeControlError("outcome_observation_tenant_mismatch")
        results = []
        for item in contract.get("expected_metrics") or []:
            metric = item["metric"]
            value = observed.get(metric)
            baseline = item.get("baseline")
            target = item.get("target")
            delta = value - baseline if isinstance(value, (int, float)) and isinstance(baseline, (int, float)) else None
            target_met = None
            if isinstance(value, (int, float)) and isinstance(target, (int, float)):
                target_met = value >= target if item.get("direction") != "decrease" else value <= target
            results.append({"metric": metric, "baseline": baseline, "target": target, "observed": value, "delta": delta, "target_met": target_met})
        report = {"version": self.VERSION, "contract_digest": contract["digest"], "results": results, "governance": {"read_only": True, "causal_claim": False, "roi_claim": False, "auto_execute": False}}
        report["digest"] = self._digest(report)
        return report


outcome_control = OutcomeControlService()
