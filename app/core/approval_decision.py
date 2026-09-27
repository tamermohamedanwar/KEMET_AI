from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ApprovalDecision:
    package_hash: str
    organization_id: int
    approver_id: int
    decision: str
    reason: str
    decision_hash: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def decide_approval(package: Any, approver_id: int, approved: bool, reason: str = "") -> ApprovalDecision:
    if approver_id <= 0:
        raise ValueError("approver_required")
    if not getattr(package, "package_hash", ""):
        raise ValueError("approval_package_required")
    decision = "approved" if approved else "rejected"
    clean_reason = str(reason).strip()
    if not approved and not clean_reason:
        raise ValueError("rejection_reason_required")
    payload = {
        "package_hash": package.package_hash,
        "organization_id": package.organization_id,
        "approver_id": approver_id,
        "decision": decision,
        "reason": clean_reason,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return ApprovalDecision(decision_hash=digest, **payload)


def verify_approval(package: Any, decision: ApprovalDecision) -> bool:
    if package.package_hash != decision.package_hash:
        return False
    if package.organization_id != decision.organization_id:
        return False
    payload = {
        "package_hash": decision.package_hash,
        "organization_id": decision.organization_id,
        "approver_id": decision.approver_id,
        "decision": decision.decision,
        "reason": decision.reason,
    }
    expected = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return expected == decision.decision_hash and decision.decision == "approved"
