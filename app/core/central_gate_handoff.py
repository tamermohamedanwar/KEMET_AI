from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from app.core.approval_decision import verify_approval


@dataclass(frozen=True)
class GateHandoff:
    organization_id: int
    plan_hash: str
    context_fingerprint: str
    package_hash: str
    decision_hash: str
    approver_id: int
    action: str
    execution_key: str
    status: str
    handoff_hash: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def create_gate_handoff(
    package: Any,
    decision: Any,
    *,
    action: str,
    execution_key: str,
) -> GateHandoff:
    if not verify_approval(package, decision):
        raise ValueError("approval_verification_failed")
    if package.organization_id != decision.organization_id:
        raise ValueError("tenant_context_mismatch")
    clean_action = str(action).strip()
    clean_key = str(execution_key).strip()
    if not clean_action or not clean_key:
        raise ValueError("gate_binding_required")
    payload = {
        "organization_id": package.organization_id,
        "plan_hash": package.plan_hash,
        "context_fingerprint": package.context_fingerprint,
        "package_hash": package.package_hash,
        "decision_hash": decision.decision_hash,
        "approver_id": decision.approver_id,
        "action": clean_action,
        "execution_key": clean_key,
        "status": "approved_for_gate",
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()
    return GateHandoff(handoff_hash=digest, **payload)


def verify_gate_handoff(
    handoff: GateHandoff,
    *,
    organization_id: int | None = None,
    plan_hash: str | None = None,
    action: str | None = None,
    execution_key: str | None = None,
) -> bool:
    if organization_id is not None and handoff.organization_id != organization_id:
        return False
    if plan_hash is not None and handoff.plan_hash != plan_hash:
        return False
    if action is not None and handoff.action != action:
        return False
    if execution_key is not None and handoff.execution_key != execution_key:
        return False
    payload = {
        "organization_id": handoff.organization_id,
        "plan_hash": handoff.plan_hash,
        "context_fingerprint": handoff.context_fingerprint,
        "package_hash": handoff.package_hash,
        "decision_hash": handoff.decision_hash,
        "approver_id": handoff.approver_id,
        "action": handoff.action,
        "execution_key": handoff.execution_key,
        "status": handoff.status,
    }
    expected = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()
    ).hexdigest()
    return expected == handoff.handoff_hash and handoff.status == "approved_for_gate"
