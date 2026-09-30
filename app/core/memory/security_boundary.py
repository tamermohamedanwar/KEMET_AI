from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


class MemorySecurityError(PermissionError):
    pass


TRUST_LEVELS = frozenset({"trusted_user", "trusted_system", "derived", "external_untrusted"})
WRITE_TRUST = frozenset({"trusted_user", "trusted_system"})


@dataclass(frozen=True)
class MemoryRecord:
    organization_id: int
    subject_id: str
    key: str
    value: Any
    trust: str
    provenance: str
    digest: str
    created_at: str
    execution_authority: bool = False

    def canonical(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "subject_id": self.subject_id,
            "key": self.key,
            "value": self.value,
            "trust": self.trust,
            "provenance": self.provenance,
            "digest": self.digest,
            "created_at": self.created_at,
            "execution_authority": False,
        }


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_memory_record(*, organization_id: int, subject_id: str, key: str, value: Any,
                         trust: str, provenance: str, now: datetime | None = None) -> MemoryRecord:
    if organization_id <= 0:
        raise MemorySecurityError("organization_required")
    if not str(subject_id).strip() or not str(key).strip():
        raise MemorySecurityError("memory_identity_required")
    if trust not in TRUST_LEVELS:
        raise MemorySecurityError("invalid_memory_trust")
    if not str(provenance).strip():
        raise MemorySecurityError("memory_provenance_required")
    if trust not in WRITE_TRUST:
        raise MemorySecurityError("untrusted_memory_write_requires_review")
    timestamp = (now or datetime.now(timezone.utc)).isoformat()
    return MemoryRecord(
        organization_id=int(organization_id), subject_id=str(subject_id), key=str(key),
        value=value, trust=trust, provenance=str(provenance), digest=_digest(value),
        created_at=timestamp,
    )


def authorize_memory_write(*, organization_id: int, subject_id: str, record: MemoryRecord) -> None:
    if record.organization_id != int(organization_id):
        raise MemorySecurityError("organization_scope_mismatch")
    if record.subject_id != str(subject_id):
        raise MemorySecurityError("subject_scope_mismatch")
    if record.execution_authority:
        raise MemorySecurityError("memory_cannot_grant_execution_authority")
    if record.trust not in WRITE_TRUST:
        raise MemorySecurityError("untrusted_memory_write_requires_review")


def verify_memory_integrity(record: MemoryRecord) -> bool:
    return record.digest == _digest(record.value) and record.execution_authority is False
