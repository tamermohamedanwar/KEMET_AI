from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import uuid4

from app import db
from app.models.durable_workforce import (
    WorkforceAssignment,
    WorkforceMembership,
    WorkforceSchedule,
    WorkforceTask,
    WorkforceTaskEvent,
)
from app.workforce.registry import workforce_registry


class DurableWorkforceOrchestration:
    VERSION = "1.0"
    SCHEMA = "kemet.durable_workforce_orchestration.v1"

    GOVERNANCE = {
        "tenant_scoped": True,
        "identity_scoped": True,
        "permission_snapshot": True,
        "delegation_scoped": True,
        "durable_history": True,
        "idempotency": True,
        "replay": True,
        "recovery": True,
        "execution_authority": False,
        "external_execution": False,
        "auto_execute": False,
        "human_approval_required": True,
        "canonical_runtime_only": True,
        "fail_closed": True,
        "mcp": False,
    }

    STATES = {
        "assigned", "planned", "approval_required", "approved", "queued",
        "processing", "executed", "result_recorded", "measured", "learned",
        "blocked", "failed", "cancelled", "expired", "retrying",
    }

    TRANSITIONS = {
        "assigned": {"planned", "blocked", "cancelled"},
        "planned": {"approval_required", "blocked", "cancelled"},
        "approval_required": {"approved", "blocked", "cancelled", "expired"},
        "approved": {"queued", "blocked", "cancelled"},
        "queued": {"processing", "expired", "cancelled"},
        "processing": {"executed", "failed", "retrying", "blocked", "cancelled"},
        "executed": {"result_recorded", "failed"},
        "result_recorded": {"measured", "failed"},
        "measured": {"learned"},
        "retrying": {"queued", "failed", "cancelled", "expired"},
        "failed": {"retrying", "cancelled"},
    }

    def _digest(self, payload: Any) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _json(self, value: Any) -> str:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)

    def _load(self, value: str | None, fallback: Any) -> Any:
        try:
            parsed = json.loads(value or "")
            return parsed
        except Exception:
            return fallback

    def membership(self, organization_id: int, workforce_id: str, *, create: bool = True):
        org = int(organization_id or 0)
        wid = str(workforce_id or "").strip().lower()
        if org <= 0 or not workforce_registry.exists(wid):
            return None
        row = WorkforceMembership.query.filter_by(organization_id=org, workforce_id=wid).first()
        if row or not create:
            return row
        profile = workforce_registry.get(wid)
        row = WorkforceMembership(
            organization_id=org,
            workforce_id=wid,
            role=str(profile.get("role", "")),
            capabilities_json=self._json(profile.get("capabilities", [])),
            allowed_actions_json=self._json(profile.get("allowed_actions", [])),
            approval_actions_json=self._json(profile.get("approval_actions", [])),
            metrics_json=self._json(profile.get("metrics", [])),
            permission_version=f"profile:{self._digest(profile)[:16]}",
        )
        db.session.add(row)
        db.session.flush()
        return row

    def permission_snapshot(self, membership: WorkforceMembership) -> dict[str, Any]:
        return {
            "workforce_id": membership.workforce_id,
            "role": membership.role,
            "capabilities": self._load(membership.capabilities_json, []),
            "allowed_actions": self._load(membership.allowed_actions_json, []),
            "approval_actions": self._load(membership.approval_actions_json, []),
            "metrics": self._load(membership.metrics_json, []),
            "permission_version": membership.permission_version,
        }

    def create_assignment(self, organization_id: int, workforce_id: str, objective: str,
                          *, idempotency_key: str | None = None, created_by: int | None = None,
                          parent_assignment_id: int | None = None) -> dict[str, Any]:
        org = int(organization_id or 0)
        key = str(idempotency_key or f"assignment:{uuid4().hex}").strip()
        objective = str(objective or "").strip()
        if org <= 0 or not objective:
            return self._blocked("organization_and_objective_required")
        membership = self.membership(org, workforce_id)
        if not membership:
            return self._blocked("workforce_not_found")
        existing = WorkforceAssignment.query.filter_by(organization_id=org, idempotency_key=key).first()
        if existing:
            return {"success": True, "status": "deduplicated", "assignment": self._assignment_dict(existing)}
        snapshot = self.permission_snapshot(membership)
        row = WorkforceAssignment(
            organization_id=org, membership_id=membership.id, workforce_id=membership.workforce_id,
            objective=objective, idempotency_key=key, permission_snapshot_json=self._json(snapshot),
            delegation_parent_id=parent_assignment_id, created_by=created_by,
        )
        db.session.add(row)
        db.session.commit()
        return {"success": True, "status": "assigned", "assignment": self._assignment_dict(row)}

    def create_task(self, organization_id: int, assignment_id: int, action: str,
                    *, input_data: dict[str, Any] | None = None,
                    idempotency_key: str | None = None) -> dict[str, Any]:
        org = int(organization_id or 0)
        assignment = WorkforceAssignment.query.filter_by(id=int(assignment_id), organization_id=org).first()
        if not assignment:
            return self._blocked("assignment_not_found")
        action = str(action or "").strip()
        snapshot = self._load(assignment.permission_snapshot_json, {})
        allowed = action in snapshot.get("allowed_actions", [])
        approval = action in snapshot.get("approval_actions", [])
        if not allowed and not approval:
            return self._blocked("action_not_allowed_for_permission_snapshot")
        key = str(idempotency_key or f"task:{uuid4().hex}").strip()
        existing = WorkforceTask.query.filter_by(organization_id=org, idempotency_key=key).first()
        if existing:
            return {"success": True, "status": "deduplicated", "task": self._task_dict(existing)}
        row = WorkforceTask(
            organization_id=org, assignment_id=assignment.id, workforce_id=assignment.workforce_id,
            action=action, state="assigned", idempotency_key=key,
            permission_snapshot_json=self._json(snapshot), input_json=self._json(input_data or {}),
        )
        db.session.add(row)
        db.session.flush()
        self._event(row, None, "assigned", "orchestrator", "task_created", {"approval_required": approval})
        db.session.commit()
        return {"success": True, "status": "assigned", "task": self._task_dict(row)}

    def transition(self, organization_id: int, task_id: int, target: str, *, actor: str,
                   reason: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        org = int(organization_id or 0)
        row = WorkforceTask.query.filter_by(id=int(task_id), organization_id=org).first()
        if not row:
            return self._blocked("task_not_found")
        target = str(target or "").strip().lower()
        current = str(row.state)
        if target not in self.STATES or target not in self.TRANSITIONS.get(current, set()):
            return self._blocked("invalid_workforce_task_transition", current_state=current, target=target)
        metadata = dict(metadata or {})
        if target == "approved" and not metadata.get("approval_id"):
            return self._blocked("approval_id_required")
        if target == "processing" and not metadata.get("execution_key"):
            return self._blocked("execution_key_required")
        if target == "executed" and not (metadata.get("evidence_digest") or metadata.get("evidence_id")):
            return self._blocked("execution_evidence_required")
        if target == "learned" and not metadata.get("learning_digest"):
            return self._blocked("learning_evidence_required")
        if target in {"approved", "processing", "executed", "result_recorded", "measured", "learned"}:
            metadata["organization_id"] = org
            metadata["task_id"] = row.id
        if metadata.get("execution_key"):
            row.execution_key = str(metadata["execution_key"])
        if metadata.get("evidence_digest"):
            row.evidence_digest = str(metadata["evidence_digest"])
        if target == "failed":
            row.last_error = str(metadata.get("error") or reason)[:4000]
        if target == "retrying":
            row.attempt += 1
        row.state = target
        if target in {"result_recorded", "measured", "learned"} and metadata.get("result") is not None:
            row.result_json = self._json(metadata["result"])
        if target == "learned":
            row.completed_at = datetime.utcnow()
        self._event(row, current, target, actor, reason, metadata)
        db.session.commit()
        return {"success": True, "status": "transitioned", "task": self._task_dict(row)}

    def schedule(self, organization_id: int, assignment_id: int, schedule_key: str,
                 schedule: dict[str, Any], *, next_run_at: datetime | None = None) -> dict[str, Any]:
        org = int(organization_id or 0)
        assignment = WorkforceAssignment.query.filter_by(id=int(assignment_id), organization_id=org).first()
        if not assignment:
            return self._blocked("assignment_not_found")
        key = str(schedule_key or "").strip()
        if not key:
            return self._blocked("schedule_key_required")
        row = WorkforceSchedule.query.filter_by(organization_id=org, schedule_key=key).first()
        if row:
            row.schedule_json = self._json(schedule or {})
            row.next_run_at = next_run_at
        else:
            row = WorkforceSchedule(organization_id=org, assignment_id=assignment.id, schedule_key=key,
                                    schedule_json=self._json(schedule or {}), next_run_at=next_run_at)
            db.session.add(row)
        db.session.commit()
        return {"success": True, "status": "scheduled", "schedule": self._schedule_dict(row)}

    def replay_preview(self, organization_id: int, task_id: int) -> dict[str, Any]:
        org = int(organization_id or 0)
        row = WorkforceTask.query.filter_by(id=int(task_id), organization_id=org).first()
        if not row:
            return self._blocked("task_not_found")
        if row.state not in {"failed", "cancelled", "expired"}:
            return self._blocked("replay_requires_recoverable_terminal_state")
        payload = {
            "task_id": row.id, "organization_id": org, "action": row.action,
            "input": self._load(row.input_json, {}), "permission_snapshot": self._load(row.permission_snapshot_json, {}),
            "source_state": row.state, "source_execution_key": row.execution_key,
        }
        return {"success": True, "status": "REPLAY_PREVIEW", "execution": False,
                "new_idempotency_key": f"replay:{row.id}:{self._digest(payload)[:20]}",
                "replay_digest": self._digest(payload), "governance": dict(self.GOVERNANCE)}

    def recover(self, organization_id: int, task_id: int, *, actor: str = "recovery") -> dict[str, Any]:
        org = int(organization_id or 0)
        row = WorkforceTask.query.filter_by(id=int(task_id), organization_id=org).first()
        if not row:
            return self._blocked("task_not_found")
        if row.state not in {"failed", "retrying"}:
            return self._blocked("task_not_recoverable")
        if row.state == "failed":
            return self.transition(org, row.id, "retrying", actor=actor, reason="durable_recovery")
        return self.transition(org, row.id, "queued", actor=actor, reason="recovery_queue_resume")

    def task(self, organization_id: int, task_id: int) -> dict[str, Any] | None:
        row = WorkforceTask.query.filter_by(id=int(task_id), organization_id=int(organization_id)).first()
        return self._task_dict(row) if row else None

    def list_tasks(self, organization_id: int, *, limit: int = 100) -> list[dict[str, Any]]:
        rows = WorkforceTask.query.filter_by(organization_id=int(organization_id)).order_by(WorkforceTask.id.desc()).limit(min(max(int(limit), 1), 500)).all()
        return [self._task_dict(row) for row in rows]

    def history(self, organization_id: int, task_id: int) -> list[dict[str, Any]]:
        rows = WorkforceTaskEvent.query.filter_by(organization_id=int(organization_id), task_id=int(task_id)).order_by(WorkforceTaskEvent.id.asc()).all()
        return [{"id": r.id, "from_state": r.from_state, "to_state": r.to_state, "actor": r.actor,
                 "reason": r.reason, "metadata_digest": r.metadata_digest, "created_at": r.created_at.isoformat()} for r in rows]

    def _event(self, task, from_state, to_state, actor, reason, metadata):
        raw = self._json(metadata)
        db.session.add(WorkforceTaskEvent(
            organization_id=task.organization_id, task_id=task.id, from_state=from_state,
            to_state=to_state, actor=str(actor)[:255], reason=str(reason)[:500],
            metadata_json=raw, metadata_digest=self._digest(metadata),
        ))

    def _blocked(self, error, **extra):
        return {"success": False, "status": "BLOCKED", "error": error, "governance": dict(self.GOVERNANCE), **extra}

    def _assignment_dict(self, row):
        return {"id": row.id, "organization_id": row.organization_id, "workforce_id": row.workforce_id,
                "objective": row.objective, "status": row.status, "idempotency_key": row.idempotency_key,
                "permission_snapshot": self._load(row.permission_snapshot_json, {}),
                "delegation_parent_id": row.delegation_parent_id, "plan_hash": row.plan_hash}

    def _task_dict(self, row):
        return {"id": row.id, "organization_id": row.organization_id, "assignment_id": row.assignment_id,
                "workforce_id": row.workforce_id, "action": row.action, "state": row.state,
                "idempotency_key": row.idempotency_key, "execution_key": row.execution_key,
                "attempt": row.attempt, "permission_snapshot": self._load(row.permission_snapshot_json, {}),
                "input": self._load(row.input_json, {}), "result": self._load(row.result_json, None),
                "evidence_digest": row.evidence_digest, "last_error": row.last_error}

    def _schedule_dict(self, row):
        return {"id": row.id, "organization_id": row.organization_id, "assignment_id": row.assignment_id,
                "schedule_key": row.schedule_key, "schedule": self._load(row.schedule_json, {}),
                "status": row.status, "next_run_at": row.next_run_at.isoformat() if row.next_run_at else None}


durable_workforce_orchestration = DurableWorkforceOrchestration()
