from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from app.core.evidence.fabric import execution_evidence_fabric


class ObservabilityControlFabric:
    VERSION = "1.0"
    SCHEMA = "kemet.observability_control_fabric.v1"
    STAGES = ("decision", "approval", "execution", "evidence", "outcome", "learning")
    SENSITIVE_KEYS = re.compile(r"(password|secret|token|api[_-]?key|authorization|cookie|client[_-]?secret)", re.I)

    def _redact(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {k: "[REDACTED]" if self.SENSITIVE_KEYS.search(str(k)) else self._redact(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._redact(v) for v in value]
        return value

    def _digest(self, value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def event(self, *, stage: str, event_name: str, correlation: dict[str, Any], outcome: str,
              attributes: dict[str, Any] | None = None) -> dict[str, Any]:
        stage_name = str(stage).strip().lower()
        if stage_name not in self.STAGES:
            raise ValueError("unsupported_observability_stage")
        trace_id = str(correlation.get("trace_id") or "").strip()
        organization_id = correlation.get("organization_id")
        if not trace_id or organization_id is None:
            raise ValueError("trace_and_organization_required")
        safe_attributes = self._redact(attributes or {})
        payload = {
            "schema": self.SCHEMA, "version": self.VERSION, "event_name": str(event_name),
            "stage": stage_name, "outcome": str(outcome), "correlation": dict(correlation),
            "attributes": safe_attributes, "observed_at": datetime.now(timezone.utc).isoformat(),
        }
        payload["event_digest"] = self._digest(payload)
        return payload

    def chain(self, *, correlation: dict[str, Any], stages: list[dict[str, Any]]) -> dict[str, Any]:
        normalized = execution_evidence_fabric.control_chain(correlation=correlation, stages=stages)
        normalized["schema"] = self.SCHEMA
        normalized["event_digest"] = self._digest(normalized)
        return normalized


observability_control_fabric = ObservabilityControlFabric()
