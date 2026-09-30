from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any

from app.models.durable_workforce import WorkforceTask, WorkforceAssignment
from app.services.decision_learning import decision_learning
from app.services.outcome_intelligence import outcome_intelligence
from app.workforce.registry import workforce_registry


class WorkforceOutcomeLearningService:
    VERSION = "1.0"
    SCHEMA = "kemet.workforce_outcome_learning.v1"
    GOVERNANCE = {
        "tenant_scoped": True,
        "read_only": True,
        "observational": True,
        "causal_claim": False,
        "roi_claim": False,
        "ranking_adjustment": "recommendation_only",
        "execution_authority": False,
        "external_execution": False,
        "auto_execute": False,
        "human_approval_required": True,
        "canonical_runtime_only": True,
        "fail_closed": True,
        "mcp": False,
    }

    def _digest(self, value: Any) -> str:
        raw = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _task_stats(self, organization_id: int, workforce_id: str, action: str | None = None):
        query = WorkforceTask.query.filter_by(organization_id=int(organization_id), workforce_id=str(workforce_id))
        if action:
            query = query.filter_by(action=str(action))
        rows = query.all()
        total = len(rows)
        successful = sum(row.state in {"executed", "result_recorded", "measured", "learned"} for row in rows)
        observed = sum(row.state in {"result_recorded", "measured", "learned"} for row in rows)
        failed = sum(row.state == "failed" for row in rows)
        return {"sample_size": total, "successful": successful, "outcome_observed": observed,
                "failed": failed, "execution_rate": round(successful / total, 4) if total else 0.0,
                "outcome_observed_rate": round(observed / successful, 4) if successful else 0.0,
                "failure_rate": round(failed / total, 4) if total else 0.0}

    def _candidate(self, organization_id: int, profile: dict[str, Any], action: str | None):
        full = workforce_registry.get(profile["id"])
        if action and action not in full.get("allowed_actions", []) and action not in full.get("approval_actions", []):
            return None
        stats = self._task_stats(organization_id, profile["id"], action)
        sample_factor = min(stats["sample_size"] / 10.0, 1.0)
        observed_quality = (0.55 * stats["execution_rate"]) + (0.45 * stats["outcome_observed_rate"])
        reliability = (0.65 * observed_quality) + (0.35 * (1.0 - stats["failure_rate"]))
        score = round((0.75 * reliability) + (0.25 * sample_factor), 4)
        return {"workforce_id": profile["id"], "role": full.get("role"),
                "capabilities": full.get("capabilities", []), "action_policy":
                "ask" if action in full.get("approval_actions", []) else "allow",
                "history": stats, "recommendation_score": score}

    def recommend(self, organization_id: int, *, objective: str, action: str | None = None,
                  capability: str | None = None, role: str | None = None) -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0 or not str(objective or "").strip():
            return {"success": False, "status": "BLOCKED", "error": "organization_and_objective_required",
                    "governance": dict(self.GOVERNANCE)}
        candidates = []
        for profile in workforce_registry.list():
            full = workforce_registry.get(profile["id"])
            if role and full.get("role") != role:
                continue
            if capability and capability not in full.get("capabilities", []):
                continue
            item = self._candidate(org, profile, action)
            if item:
                candidates.append(item)
        if not candidates:
            return {"success": False, "status": "BLOCKED", "error": "no_eligible_workforce",
                    "governance": dict(self.GOVERNANCE)}
        candidates.sort(key=lambda item: (-item["recommendation_score"], item["workforce_id"]))
        return {"success": True, "status": "RECOMMENDATION_READY", "organization_id": org,
                "objective": str(objective).strip(), "action": action, "candidates": candidates,
                "recommended": candidates[0], "execution": False,
                "approval_required": True, "governance": dict(self.GOVERNANCE),
                "generated_at": datetime.utcnow().isoformat(),
                "recommendation_digest": self._digest(candidates)}

    def learning_snapshot(self, organization_id: int, *, action: str | None = None,
                          period: str = "30d") -> dict[str, Any]:
        org = int(organization_id or 0)
        if org <= 0:
            return {"success": False, "status": "BLOCKED", "error": "organization_required",
                    "governance": dict(self.GOVERNANCE)}
        workforce = []
        for profile in workforce_registry.list():
            stats = self._task_stats(org, profile["id"], action)
            workforce.append({"workforce_id": profile["id"], "role": workforce_registry.get(profile["id"]).get("role"), "history": stats})
        intelligence = []
        for capability_id in list(outcome_intelligence.SIGNALS):
            if action and capability_id != f"kemet.{action}":
                continue
            item = outcome_intelligence.build(org, capability_id, period)
            if item.get("success"):
                intelligence.append({"capability_id": capability_id, "confidence": item["confidence"],
                                     "observed_impact": item["observed_impact"], "attribution": item["attribution"]})
        decision_signal = decision_learning.build(org, [], period)
        payload = {"success": True, "status": "LEARNING_SNAPSHOT_READY", "schema": self.SCHEMA, "version": self.VERSION, "organization_id": org,
                   "period": period, "workforce": workforce, "outcome_intelligence": intelligence,
                   "decision_learning": decision_signal.get("aggregate", {}),
                   "governance": dict(self.GOVERNANCE), "generated_at": datetime.utcnow().isoformat()}
        payload["snapshot_digest"] = self._digest(payload)
        return payload


workforce_outcome_learning = WorkforceOutcomeLearningService()
