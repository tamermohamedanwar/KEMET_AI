from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from app.models.durable_workforce import WorkforceAssignment, WorkforceTask, WorkforceSchedule
from app.services.corporate_force_card import corporate_force_card
from app.services.governed_workforce_orchestration import governed_workforce_orchestration
from app.workforce.registry import workforce_registry


class CorporateForceCardV4Service:
    VERSION = "4.0"
    SCHEMA = "kemet.corporate_force_card.v4"
    GOVERNANCE = {
        "identity_scoped": True,
        "tenant_scoped": True,
        "hierarchy_scoped": True,
        "dependency_scoped": True,
        "approval_bound": True,
        "execution_authority": False,
        "external_execution": False,
        "auto_execute": False,
        "human_approval_required": True,
        "canonical_runtime_only": True,
        "fail_closed": True,
        "mcp": False,
    }

    def _digest(self, payload: Any) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":"))
        return sha256(raw.encode("utf-8")).hexdigest()

    def build(self, organization_id: int, workforce_id: str) -> dict[str, Any]:
        base = corporate_force_card.build(organization_id, workforce_id)
        if base.get("status") == "BLOCKED":
            return base
        assignments = WorkforceAssignment.query.filter_by(organization_id=int(organization_id), workforce_id=str(workforce_id)).order_by(WorkforceAssignment.id.desc()).limit(100).all()
        tasks = WorkforceTask.query.filter_by(organization_id=int(organization_id), workforce_id=str(workforce_id)).order_by(WorkforceTask.id.desc()).limit(200).all()
        schedules = WorkforceSchedule.query.filter_by(organization_id=int(organization_id)).order_by(WorkforceSchedule.id.desc()).limit(100).all()
        payload = {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "organization_id": int(organization_id),
            "identity": base["identity"],
            "role": base["role"],
            "hierarchy": [{"assignment_id": a.id, "parent_assignment_id": a.delegation_parent_id,
                           "status": a.status, "plan_hash": a.plan_hash} for a in assignments],
            "work": [{"task_id": t.id, "assignment_id": t.assignment_id, "action": t.action,
                      "state": t.state, "attempt": t.attempt,
                      "dependencies": json.loads(t.input_json or "{}").get("depends_on", [])} for t in tasks],
            "approvals": [{"assignment_id": a.id, "plan_hash": a.plan_hash,
                           "approval_required": bool(a.plan_hash)} for a in assignments if a.status in {"planned", "approval_required"}],
            "schedules": [{"id": s.id, "assignment_id": s.assignment_id, "status": s.status,
                           "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None} for s in schedules
                          if any(a.id == s.assignment_id for a in assignments)],
            "governance": dict(self.GOVERNANCE),
            "orchestration": governed_workforce_orchestration.orchestration_snapshot(int(organization_id)),
        }
        payload["card_digest"] = self._digest(payload)
        return payload

    def build_team(self, organization_id: int) -> dict[str, Any]:
        cards = [self.build(organization_id, profile["id"]) for profile in workforce_registry.list()]
        payload = {"schema": self.SCHEMA, "version": self.VERSION,
                   "organization_id": int(organization_id), "cards": cards,
                   "card_count": len(cards), "governance": dict(self.GOVERNANCE)}
        payload["team_digest"] = self._digest(payload)
        return payload


corporate_force_card_v4 = CorporateForceCardV4Service()
