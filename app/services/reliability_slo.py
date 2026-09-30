from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SLODefinition:
    name: str
    indicator: str
    target: float
    window: str = "30d"
    unit: str = "ratio"

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "indicator": self.indicator, "target": self.target,
                "window": self.window, "unit": self.unit}


class ReliabilitySLOService:
    VERSION = "1.0"
    SCHEMA = "kemet.reliability_slo.v1"
    DEFINITIONS = (
        SLODefinition("http_availability", "successful_http_requests", 0.995),
        SLODefinition("api_p95_latency", "requests_with_latency_le_1_5s", 0.95),
        SLODefinition("api_p99_latency", "requests_with_latency_le_3s", 0.99),
        SLODefinition("error_rate", "successful_requests", 0.995),
        SLODefinition("db_success_rate", "successful_db_operations", 0.999),
        SLODefinition("task_success_rate", "successful_workforce_tasks", 0.99),
        SLODefinition("provider_success_rate", "successful_provider_requests", 0.99),
        SLODefinition("approval_execution_traceability", "executions_with_bound_approval", 1.0),
        SLODefinition("evidence_integrity", "valid_evidence_digests", 1.0),
    )

    def catalog(self) -> dict[str, Any]:
        return {"schema": self.SCHEMA, "version": self.VERSION,
                "measurement_only": True, "policy_separate": True,
                "execution_authority": False,
                "slos": [item.as_dict() for item in self.DEFINITIONS]}

    def evaluate(self, observations: dict[str, Any]) -> dict[str, Any]:
        results = []
        for item in self.DEFINITIONS:
            value = observations.get(item.indicator)
            if value is None:
                results.append({"name": item.name, "status": "UNMEASURED", "target": item.target})
                continue
            numeric = float(value)
            results.append({"name": item.name, "status": "MEETS" if numeric >= item.target else "MISSES",
                            "value": numeric, "target": item.target})
        return {"schema": self.SCHEMA, "version": self.VERSION, "results": results,
                "error_budget_policy": "advisory_only", "execution": False}


reliability_slo = ReliabilitySLOService()
