from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ConnectorContract:
    """Declarative contract for external channels behind Kemet governance."""

    connector_id: str
    version: str = "1.0"
    organization_id: int | None = None
    operations: tuple[str, ...] = ()
    data_scopes: tuple[str, ...] = ()
    risk_tier: str = "critical"
    approval_level: str = "human"
    idempotency: str = "required"
    timeout_seconds: int = 30
    max_retries: int = 0
    reversible: bool = False
    evidence_required: bool = True
    attestation_required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> dict[str, Any]:
        errors: list[str] = []
        if not self.connector_id.strip():
            errors.append("connector_id_required")
        if self.risk_tier not in {"low", "medium", "high", "critical"}:
            errors.append("invalid_risk_tier")
        if self.approval_level not in {"none", "human", "human_critical"}:
            errors.append("invalid_approval_level")
        if self.idempotency not in {"required", "best_effort"}:
            errors.append("invalid_idempotency")
        if self.timeout_seconds <= 0:
            errors.append("invalid_timeout")
        if self.max_retries < 0:
            errors.append("invalid_retry_policy")
        if self.risk_tier in {"high", "critical"} and self.approval_level == "none":
            errors.append("high_risk_requires_approval")
        if self.risk_tier in {"medium", "high", "critical"} and not self.evidence_required:
            errors.append("side_effects_require_evidence")
        if self.risk_tier == "critical" and not self.attestation_required:
            errors.append("critical_requires_attestation")
        return {"valid": not errors, "errors": errors}

    def allows(self, operation: str, organization_id: int) -> bool:
        return (
            self.validate()["valid"]
            and self.organization_id == organization_id
            and operation in self.operations
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "version": self.version,
            "organization_id": self.organization_id,
            "operations": list(self.operations),
            "data_scopes": list(self.data_scopes),
            "risk_tier": self.risk_tier,
            "approval_level": self.approval_level,
            "idempotency": self.idempotency,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "reversible": self.reversible,
            "evidence_required": self.evidence_required,
            "attestation_required": self.attestation_required,
        }
