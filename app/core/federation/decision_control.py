from __future__ import annotations

from hashlib import sha256
import json
from typing import Any


class DecisionControlError(ValueError):
    pass


class DecisionControlService:
    VERSION = "1.0"
    STATUSES = ("proposed", "review_required", "approved", "rejected", "executed", "measured")

    @staticmethod
    def _digest(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return sha256(raw.encode("utf-8")).hexdigest()

    def create(self, *, task_id: str, organization_id: int, brief: dict[str, Any],
               plan_hash: str = "", project_context_hash: str = "") -> dict[str, Any]:
        if not task_id or int(organization_id) <= 0 or not isinstance(brief, dict):
            raise DecisionControlError("decision_identity_required")
        brief_digest = str(brief.get("digest") or "")
        trace = brief.get("traceability") if isinstance(brief.get("traceability"), dict) else {}
        if not brief_digest:
            raise DecisionControlError("executive_brief_digest_required")
        decision = {
            "version": self.VERSION, "type": "governed_decision_record",
            "decision_id": f"decision-{task_id}-{brief_digest[:12]}",
            "task_id": task_id, "organization_id": int(organization_id),
            "status": "review_required", "brief_digest": brief_digest,
            "evidence_digest": str(trace.get("research_evidence_digest") or ""),
            "project_context_hash": str(project_context_hash or ""), "plan_hash": str(plan_hash or ""),
            "recommendation": str(brief.get("decision", {}).get("recommendation") or ""),
            "human_review_required": True, "auto_execute": False,
            "governance": {"read_only": True, "external_execution": False, "database_mutation": False},
        }
        decision["digest"] = self._digest(decision)
        return decision


decision_control = DecisionControlService()
