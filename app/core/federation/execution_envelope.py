import hashlib
import json
from typing import Any, Mapping


class ExecutionEnvelopeError(ValueError):
    pass


class ExecutionEnvelope:
    VERSION = "1.2"

    @staticmethod
    def _canonical(payload: Mapping[str, Any]) -> str:
        return json.dumps(dict(payload), sort_keys=True, separators=(",", ":"))

    def build(
        self, *, approval_package_hash: str, decision_hash: str,
        handoff_hash: str, authorization: Mapping[str, Any],
        execution_key: str, provider_id: str, action: str,
        evidence_context_hash: str = "", outcome_contract_digest: str = "",
        artifact_preview_digest: str = "",
    ) -> dict[str, Any]:
        plan_hash = str(authorization.get("plan_hash") or "")
        auth_id = str(authorization.get("plan_id") or "")
        if not all([approval_package_hash, decision_hash, handoff_hash,
                    plan_hash, auth_id, execution_key, provider_id, action]):
            raise ExecutionEnvelopeError("execution_envelope_identity_required")
        payload = {
            "version": self.VERSION,
            "approval_package_hash": str(approval_package_hash),
            "decision_hash": str(decision_hash),
            "handoff_hash": str(handoff_hash),
            "authorization_plan_hash": plan_hash,
            "authorization_plan_id": auth_id,
            "execution_key": str(execution_key),
            "provider_id": str(provider_id),
            "action": str(action),
        }
        if evidence_context_hash:
            payload["evidence_context_hash"] = str(evidence_context_hash)
        if outcome_contract_digest:
            payload["outcome_contract_digest"] = str(outcome_contract_digest)
        if artifact_preview_digest:
            payload["artifact_preview_digest"] = str(artifact_preview_digest)
        payload["envelope_hash"] = hashlib.sha256(
            self._canonical(payload).encode()
        ).hexdigest()
        return payload

    def verify(
        self, envelope: Mapping[str, Any], *, authorization: Mapping[str, Any],
        execution_key: str, provider_id: str, action: str,
        approval_package_hash: str | None = None,
        decision_hash: str | None = None,
        handoff_hash: str | None = None,
        evidence_context_hash: str | None = None,
        outcome_contract_digest: str | None = None,
        artifact_preview_digest: str | None = None,
    ) -> bool:
        try:
            if str(envelope.get("execution_key")) != str(execution_key):
                return False
            if str(envelope.get("provider_id")) != str(provider_id):
                return False
            if str(envelope.get("action")) != str(action):
                return False
            if str(envelope.get("authorization_plan_hash")) != str(authorization.get("plan_hash")):
                return False
            if str(envelope.get("authorization_plan_id")) != str(authorization.get("plan_id")):
                return False
            if decision_hash is not None and str(envelope.get("decision_hash") or "") != str(decision_hash):
                return False
            if str(envelope.get("version")) != self.VERSION:
                return False
            if approval_package_hash is not None and str(envelope.get("approval_package_hash") or "") != str(approval_package_hash):
                return False
            if handoff_hash is not None and str(envelope.get("handoff_hash") or "") != str(handoff_hash):
                return False
            if evidence_context_hash is not None and str(envelope.get("evidence_context_hash") or "") != str(evidence_context_hash):
                return False
            if outcome_contract_digest is not None and str(envelope.get("outcome_contract_digest") or "") != str(outcome_contract_digest):
                return False
            if artifact_preview_digest is not None and str(envelope.get("artifact_preview_digest") or "") != str(artifact_preview_digest):
                return False
            supplied = envelope.get("envelope_hash")
            expected = dict(envelope)
            expected.pop("envelope_hash", None)
            return bool(supplied) and str(supplied) == hashlib.sha256(
                self._canonical(expected).encode()
            ).hexdigest()
        except Exception:
            return False


execution_envelope = ExecutionEnvelope()
