from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any

from app.core.secret_boundary import redact


class DataBoundaryError(ValueError):
    pass


@dataclass(frozen=True)
class DataEntitlement:
    provider_id: str
    dataset: str
    organization_id: int
    allowed_operations: tuple[str, ...] = ()
    model_use_allowed: bool = True
    export_allowed: bool = False
    training_allowed: bool = False
    citation_required: bool = True
    retention: str = "task"
    policy_version: str = "1"

    def allows(self, operation: str) -> bool:
        return operation in self.allowed_operations

    def fingerprint(self) -> str:
        payload = {
            "provider_id": self.provider_id,
            "dataset": self.dataset,
            "organization_id": self.organization_id,
            "allowed_operations": sorted(self.allowed_operations),
            "model_use_allowed": self.model_use_allowed,
            "export_allowed": self.export_allowed,
            "training_allowed": self.training_allowed,
            "citation_required": self.citation_required,
            "retention": self.retention,
            "policy_version": self.policy_version,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


@dataclass(frozen=True)
class EvidenceRecord:
    source_id: str
    source_type: str
    locator: str | None = None
    claim: str | None = None
    transformation: str | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "locator": self.locator,
            "claim": self.claim,
            "transformation": self.transformation,
            "confidence": self.confidence,
            "metadata": _safe_metadata(self.metadata),
        }


@dataclass(frozen=True)
class BoundaryContext:
    organization_id: int
    user_id: int
    task_id: str
    provider_id: str
    dataset: str
    operation: str
    fields: tuple[str, ...]
    values: dict[str, Any]
    evidence: tuple[EvidenceRecord, ...]
    entitlement: DataEntitlement
    policy_version: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "task_id": self.task_id,
            "provider_id": self.provider_id,
            "dataset": self.dataset,
            "operation": self.operation,
            "fields": list(self.fields),
            "values": self.values,
            "evidence": [item.as_dict() for item in self.evidence],
            "policy_version": self.policy_version,
        }

    def fingerprint(self) -> str:
        payload = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(payload.encode()).hexdigest()


def _safe_metadata(value: dict[str, Any]) -> dict[str, Any]:
    blocked = ("token", "secret", "password", "api_key", "authorization", "cookie")
    return {k: v for k, v in value.items() if not any(x in k.lower() for x in blocked)}


class DataBoundary:
    """Fail-closed boundary for minimum model-visible business context."""

    VERSION = "1.0"

    def resolve(
        self,
        *,
        organization_id: int,
        user_id: int,
        task_id: str,
        provider_id: str,
        dataset: str,
        operation: str,
        entitlement: DataEntitlement,
        source: dict[str, Any],
        fields: tuple[str, ...],
    ) -> BoundaryContext:
        if organization_id <= 0 or user_id <= 0:
            raise DataBoundaryError("invalid_identity")
        if entitlement.organization_id != organization_id:
            raise DataBoundaryError("tenant_mismatch")
        if entitlement.provider_id != provider_id or entitlement.dataset != dataset:
            raise DataBoundaryError("entitlement_mismatch")
        if not entitlement.allows(operation):
            raise DataBoundaryError("operation_not_entitled")
        if not entitlement.model_use_allowed:
            raise DataBoundaryError("model_use_not_allowed")
        missing = [field for field in fields if field not in source]
        if missing:
            raise DataBoundaryError("required_field_missing")

        values = redact({field: source[field] for field in fields})
        evidence = EvidenceRecord(
            source_id=f"{provider_id}:{dataset}",
            source_type="boundary_source",
            locator=source.get("locator"),
            transformation="minimum_required_fields",
            metadata={"fields": list(fields), "operation": operation},
        )
        return BoundaryContext(
            organization_id=organization_id,
            user_id=user_id,
            task_id=task_id,
            provider_id=provider_id,
            dataset=dataset,
            operation=operation,
            fields=fields,
            values=values,
            evidence=(evidence,),
            entitlement=entitlement,
            policy_version=entitlement.policy_version,
        )


data_boundary = DataBoundary()
