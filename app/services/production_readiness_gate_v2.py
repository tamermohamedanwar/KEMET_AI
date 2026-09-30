from __future__ import annotations

from typing import Any


class ProductionReadinessGateV2:
    VERSION = "2.0"
    SCHEMA = "kemet.production_readiness_gate.v2"
    REQUIRED = ("architecture", "security", "reliability", "data_integrity", "quality", "runtime", "documentation")

    def evaluate(self, evidence: dict[str, Any]) -> dict[str, Any]:
        checks = []
        for key in self.REQUIRED:
            value = evidence.get(key)
            if isinstance(value, dict):
                ok = bool(value.get("ok"))
            else:
                ok = bool(value)
            checks.append({"gate": key, "ok": ok})
        all_ok = all(item["ok"] for item in checks)
        return {"schema": self.SCHEMA, "version": self.VERSION, "status": "READY" if all_ok else "BLOCKED",
                "production_ready": all_ok, "checks": checks,
                "mcp": False, "second_executor": False, "human_approval_required": True,
                "canonical_runtime_only": True, "fail_closed": True}


production_readiness_gate_v2 = ProductionReadinessGateV2()
