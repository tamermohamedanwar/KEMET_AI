from __future__ import annotations

from hashlib import sha256
import json
from typing import Any, Mapping

from app import db
from app.core.execution_ledger import execution_ledger
from app.core.execution_evidence import execution_evidence
from app.core.federation.outcome_control import OutcomeControlError, outcome_control
from app.models.external_task import ExternalTaskRecord


class OutcomeLifecycleError(ValueError):
    pass


class OutcomeLifecycleService:
    VERSION = "1.0"

    @staticmethod
    def _digest(value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
        return sha256(raw.encode("utf-8")).hexdigest()

    def bind_contract(self, *, contract: Mapping[str, Any], organization_id: int,
                      execution_key: str, provider_id: str, evidence_context_hash: str,
                      measurement_context: Mapping[str, Any],
                      require_execution_binding: bool = True) -> dict[str, Any]:
        try:
            outcome_control._validate_contract(dict(contract))
        except OutcomeControlError as exc:
            raise OutcomeLifecycleError(str(exc)) from exc
        if int(contract["organization_id"]) != int(organization_id):
            raise OutcomeLifecycleError("outcome_contract_tenant_mismatch")
        task_id = str(contract.get("task_id") or "")
        if not execution_key or not provider_id or not evidence_context_hash or not task_id:
            raise OutcomeLifecycleError("outcome_lifecycle_identity_required")
        row = ExternalTaskRecord.query.filter_by(organization_id=int(organization_id), execution_key=str(execution_key)).first()
        if not row:
            raise OutcomeLifecycleError("external_task_not_found")
        if row.provider_id != str(provider_id):
            raise OutcomeLifecycleError("outcome_provider_mismatch")
        contract_decision_hash = str(contract.get("decision_hash") or "")
        if not contract_decision_hash:
            raise OutcomeLifecycleError("outcome_decision_hash_required")
        ledger = execution_ledger.get(organization_id=int(organization_id), execution_key=str(execution_key))
        if require_execution_binding and not ledger:
            raise OutcomeLifecycleError("execution_receipt_not_found")
        receipt = dict((ledger or {}).get("receipt") or {})
        ledger_decision_hash = str((receipt.get("execution_identity") or {}).get("decision_hash") or "")
        if require_execution_binding and ledger_decision_hash != contract_decision_hash:
            raise OutcomeLifecycleError("outcome_decision_hash_binding_mismatch")
        receipt_digest = execution_ledger.receipt_digest(receipt) if ledger else ""
        evidence_rows = execution_evidence.history(organization_id=int(organization_id), execution_key=str(execution_key))
        submitted = next((item for item in reversed(evidence_rows) if item.get("stage") == "specialist.execution_submitted"), None)
        if require_execution_binding and not submitted:
            raise OutcomeLifecycleError("execution_evidence_not_found")
        evidence_binding = self._digest({
            "organization_id": int(organization_id),
            "execution_key": str(execution_key),
            "provider_id": str(provider_id),
            "plan_hash": str(row.plan_hash),
            "stage": submitted.get("stage") if submitted else "",
            "status": submitted.get("status") if submitted else "",
            "receipt": submitted.get("receipt") if submitted else {},
        })
        state = {
            "version": self.VERSION,
            "contract_digest": str(contract["digest"]),
            "decision_id": str(contract["decision_id"]),
            "decision_hash": contract_decision_hash,
            "task_id": task_id,
            "organization_id": int(organization_id),
            "execution_key": str(execution_key),
            "provider_id": str(provider_id),
            "evidence_context_hash": str(evidence_context_hash),
            "execution_receipt_digest": receipt_digest,
            "execution_evidence_binding_digest": evidence_binding,
            "measurement_context": dict(measurement_context or {}),
            "measurement_context_digest": self._digest(dict(measurement_context or {})),
            "measurement_count": 0,
            "status": "bound",
        }
        metadata = json.loads(row.metadata_json or "{}")
        bound_task_id = metadata.get("task_id")
        if bound_task_id is not None and str(bound_task_id) != task_id:
            raise OutcomeLifecycleError("outcome_task_mismatch")
        existing = metadata.get("outcome_lifecycle")
        if existing:
            immutable_keys = (
                "contract_digest", "decision_id", "decision_hash", "task_id", "organization_id",
                "execution_key", "provider_id", "evidence_context_hash",
                "execution_receipt_digest", "execution_evidence_binding_digest",
                "measurement_context_digest",
            )
            if all(existing.get(key) == state.get(key) for key in immutable_keys):
                return existing
            raise OutcomeLifecycleError("outcome_lifecycle_identity_conflict")
        metadata["outcome_lifecycle"] = state
        row.metadata_json = json.dumps(metadata, ensure_ascii=False, default=str)
        db.session.commit()
        return state

    def measure(self, *, organization_id: int, execution_key: str, provider_id: str,
                contract_digest: str, evidence_context_hash: str,
                measurement_context: Mapping[str, Any], observed: Mapping[str, Any]) -> dict[str, Any]:
        row = ExternalTaskRecord.query.filter_by(organization_id=int(organization_id), execution_key=str(execution_key)).first()
        if not row:
            raise OutcomeLifecycleError("external_task_not_found")
        metadata = json.loads(row.metadata_json or "{}")
        state = metadata.get("outcome_lifecycle")
        if not isinstance(state, dict):
            raise OutcomeLifecycleError("outcome_lifecycle_not_bound")
        checks = (
            ("provider_id", str(provider_id), str(state.get("provider_id"))),
            ("contract_digest", str(contract_digest), str(state.get("contract_digest"))),
            ("evidence_context_hash", str(evidence_context_hash), str(state.get("evidence_context_hash"))),
        )
        for name, supplied, expected in checks:
            if supplied != expected:
                raise OutcomeLifecycleError(f"outcome_{name}_mismatch")
        ledger = execution_ledger.get(organization_id=int(organization_id), execution_key=str(execution_key))
        if not ledger:
            raise OutcomeLifecycleError("execution_receipt_not_found")
        receipt = dict(ledger.get("receipt") or {})
        ledger_decision_hash = str((receipt.get("execution_identity") or {}).get("decision_hash") or "")
        if ledger_decision_hash != str(state.get("decision_hash")):
            raise OutcomeLifecycleError("outcome_decision_hash_binding_mismatch")
        if str(state.get("execution_receipt_digest")) != execution_ledger.receipt_digest(receipt):
            raise OutcomeLifecycleError("execution_receipt_binding_mismatch")
        evidence_rows = execution_evidence.history(organization_id=int(organization_id), execution_key=str(execution_key))
        submitted = next((item for item in reversed(evidence_rows) if item.get("stage") == "specialist.execution_submitted"), None)
        if not submitted:
            raise OutcomeLifecycleError("execution_evidence_not_found")
        evidence_binding = self._digest({
            "organization_id": int(organization_id),
            "execution_key": str(execution_key),
            "provider_id": str(provider_id),
            "plan_hash": str(row.plan_hash),
            "stage": submitted.get("stage"),
            "status": submitted.get("status"),
            "receipt": submitted.get("receipt") or {},
        })
        if str(state.get("execution_evidence_binding_digest")) != evidence_binding:
            raise OutcomeLifecycleError("execution_evidence_binding_mismatch")
        context_digest = self._digest(dict(measurement_context or {}))
        if context_digest != str(state.get("measurement_context_digest")):
            raise OutcomeLifecycleError("stale_measurement_context")
        if not isinstance(observed, Mapping):
            raise OutcomeLifecycleError("observed_metrics_required")
        observed_execution = observed.get("execution_key")
        observed_provider = observed.get("provider_id")
        if observed_execution is not None and str(observed_execution) != str(execution_key):
            raise OutcomeLifecycleError("outcome_execution_key_mismatch")
        if observed_provider is not None and str(observed_provider) != str(provider_id):
            raise OutcomeLifecycleError("outcome_provider_result_substitution")
        payload = dict(observed)
        payload.pop("execution_key", None)
        payload.pop("provider_id", None)
        observation_digest = self._digest(payload)
        previous = metadata.get("outcome_measurements") or []
        if any(item.get("observation_digest") == observation_digest for item in previous):
            raise OutcomeLifecycleError("outcome_measurement_replay")
        previous.append({"observation_digest": observation_digest, "context_digest": context_digest,
                         "provider_id": str(provider_id), "contract_digest": str(contract_digest), "observed": payload})
        state["measurement_count"] = len(previous)
        state["status"] = "measured"
        metadata["outcome_lifecycle"] = state
        metadata["outcome_measurements"] = previous
        row.metadata_json = json.dumps(metadata, ensure_ascii=False, default=str)
        db.session.commit()
        return {"version": self.VERSION, "status": state["status"], "measurement_count": len(previous),
                "contract_digest": str(contract_digest), "observation_digest": observation_digest,
                "governance": {"read_only": True, "causal_claim": False, "roi_claim": False, "auto_execute": False},
                "observed": payload}


outcome_lifecycle = OutcomeLifecycleService()
