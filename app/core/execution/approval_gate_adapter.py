from __future__ import annotations

import hashlib
import json
from app.core.central_gate_handoff import GateHandoff


def _digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def create_runtime_handoff(plan, *, approver_id, execution_key):
    org = int((plan.get("context") or {}).get("organization_id") or 0)
    if org <= 0 or int(approver_id or 0) <= 0:
        raise ValueError("gate_identity_required")
    plan_hash = str(plan.get("plan_hash") or "")
    action = str(plan.get("action") or "").strip()
    if not plan_hash or not action or not execution_key:
        raise ValueError("gate_binding_required")
    context = _digest(plan.get("context") or {})
    package_hash = _digest({"organization_id": org, "plan_hash": plan_hash, "context": context, "action": action})
    decision_hash = _digest({"package_hash": package_hash, "organization_id": org, "approver_id": approver_id, "decision": "approved"})
    payload = {"organization_id": org, "plan_hash": plan_hash, "context_fingerprint": context,
               "package_hash": package_hash, "decision_hash": decision_hash, "approver_id": int(approver_id),
               "action": action, "execution_key": str(execution_key), "status": "approved_for_gate"}
    return GateHandoff(handoff_hash=_digest(payload), **payload)
