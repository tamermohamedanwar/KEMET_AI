from __future__ import annotations

import hashlib
import json
from typing import Any


class WorkforceOutcomeAttributionV2:
    VERSION = "2.0"
    SCHEMA = "kemet.workforce_outcome_attribution.v2"

    def _digest(self, value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    def build(self, *, organization_id: int, workforce_id: str, assignment_id: str,
              task_id: str, execution_id: str | None, evidence_id: str | None,
              observed_outcome: dict[str, Any] | None) -> dict[str, Any]:
        if int(organization_id) <= 0 or not workforce_id or not assignment_id or not task_id:
            return {"success": False, "status": "BLOCKED", "error": "identity_binding_required"}
        identity = {"organization_id": int(organization_id), "workforce_id": str(workforce_id),
                    "assignment_id": str(assignment_id), "task_id": str(task_id),
                    "execution_id": str(execution_id) if execution_id else None,
                    "evidence_id": str(evidence_id) if evidence_id else None}
        complete = bool(execution_id and evidence_id and observed_outcome is not None)
        result = {"success": True, "status": "OBSERVED" if complete else "IDENTITY_BOUND",
                  "schema": self.SCHEMA, "version": self.VERSION, "identity": identity,
                  "observed_outcome": observed_outcome,
                  "attribution": {"causal": False, "roi": False, "revenue": False,
                                  "level": "observed" if complete else "not_attributed"},
                  "governance": {"read_only": True, "recommendation_only": True,
                                 "execution_authority": False, "human_approval_required": True}}
        result["attribution_digest"] = self._digest(result)
        return result


workforce_outcome_attribution_v2 = WorkforceOutcomeAttributionV2()
