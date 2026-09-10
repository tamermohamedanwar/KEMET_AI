from __future__ import annotations

import hashlib
import json
from typing import Any


class EvidenceFabric:
    """Create deterministic, tamper-evident execution evidence."""

    VERSION = "1.0"

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> str:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        )

    def digest(self, payload: dict[str, Any]) -> str:
        return hashlib.sha256(self._canonical(payload).encode("utf-8")).hexdigest()

    def execution_record(
        self,
        *,
        action: str,
        plan_hash: str | None,
        risk: dict[str, Any],
        result: dict[str, Any],
    ) -> dict[str, Any]:
        evidence = {
            "version": self.VERSION,
            "type": "execution_evidence",
            "action": action,
            "plan_hash": plan_hash,
            "risk": risk,
            "status": result.get("status"),
            "success": bool(result.get("success")),
            "executed": bool(result.get("executed")),
        }
        return {**evidence, "digest": self.digest(evidence)}


execution_evidence_fabric = EvidenceFabric()
