from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

from app import db
from app.models.durable_workforce import (
    WorkforceAssignment,
    WorkforceTask,
    WorkforceSchedule,
)
from app.services.durable_workforce_orchestration import durable_workforce_orchestration
from app.workforce.registry import workforce_registry


class GovernedWorkforceOrchestration:
    VERSION = "1.0"
    SCHEMA = "kemet.governed_workforce_orchestration.v1"
    GOVERNANCE = {
        "tenant_scoped": True,
        "permission_bound": True,
        "delegation_cycle_protection": True,
        "dependency_aware": True,
        "approval_bundle_binding": True,
        "durable_schedule": True,
        "recovery": True,
        "replay_only": True,
        "execution_authority": False,
        "external_execution": False,
        "auto_execute": False,
        "human_approval_required": True,
        "canonical_runtime_only": True,
        "fail_closed": True,
        "mcp": False,
    }

    def _json(self, value: Any) -> str:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)

    def _load(self, value: str | None, fallback: Any) -> Any:
        try:
            return json.loads(value or "")
        except Exception:
            return fallback

    def _digest(self, value: Any) -> str:
        return hashlib.sha256(self._json(value).encode("utf-8")).hexdigest()

    def _blocked(self, error: str, **extra) -> dict[str, Any]:
        return {"success": False, "status": "BLOCKED", "error": error,
                "governance": dict(self.GOVERNANCE), **extra}

    def _org(self, organization_id: int) -> int | None:
        value = int(organization_id or 0)
        return value if value > 0 else None

    def _assignment(self, org: int, assignment_id: int):
        return WorkforceAssignment.query.filter_by(id=int(assignment_id), organization_id=org).first()

    def delegate(self, organization_id: int, parent_assignment_id: int,
                 workforce_id: str, objective: str, *, idempotency_key: str | None = None,
                 created_by: int | None = None) -> dict[str, Any]:
        org = self._org(organization_id)
        if not org or not objective or not workforce_registry.exists(workforce_id):
            return self._blocked("invalid_delegation_request")
        parent = self._assignment(org, parent_assignment_id)
        if not parent:
            return self._blocked("parent_assignment_not_found")
        if parent.workforce_id == str(workforce_id).strip().lower():
            return self._blocked("self_delegation_blocked")
        seen = {parent.id}
        cursor = parent
        while cursor.delegation_parent_id:
            if cursor.delegation_parent_id in seen:
                return self._blocked("delegation_cycle_detected")
            seen.add(cursor.delegation_parent_id)
            cursor = self._assignment(org, cursor.delegation_parent_id)
            if not cursor:
                return self._blocked("delegation_parent_chain_invalid")
        parent_snapshot = self._load(parent.permission_snapshot_json, {})
        allowed_caps = set(parent_snapshot.get("capabilities", []))
        child_profile = workforce_registry.get(workforce_id)
        if not allowed_caps.intersection(child_profile.get("capabilities", [])):
            return self._blocked("delegation_capability_mismatch")
        result = durable_workforce_orchestration.create_assignment(
            org, workforce_id, objective, idempotency_key=idempotency_key,
            created_by=created_by, parent_assignment_id=parent.id,
        )
        if result.get("success"):
            child = self._assignment(org, result["assignment"]["id"])
            child.status = "assigned"
            db.session.commit()
        return result

    def select(self, organization_id: int, *, objective: str, action: str | None = None,
               role: str | None = None, capability: str | None = None) -> dict[str, Any]:
        org = self._org(organization_id)
        if not org or not str(objective or "").strip():
            return self._blocked("objective_required")
        candidates = []
        for profile in workforce_registry.list():
            full = workforce_registry.get(profile["id"])
            if role and full.get("role") != role:
                continue
            if capability and capability not in full.get("capabilities", []):
                continue
            if action and action not in full.get("allowed_actions", []) and action not in full.get("approval_actions", []):
                continue
            candidates.append({"id": profile["id"], "role": full.get("role"),
                               "capabilities": full.get("capabilities", []),
                               "action_policy": "ask" if action in full.get("approval_actions", []) else "allow"})
        if not candidates:
            return self._blocked("no_policy_compatible_workforce")
        return {"success": True, "status": "SELECTED", "organization_id": org,
                "selection": candidates[0], "candidates": candidates,
                "execution": False, "governance": dict(self.GOVERNANCE)}

    def plan(self, organization_id: int, assignment_id: int, tasks: list[dict[str, Any]]) -> dict[str, Any]:
        org = self._org(organization_id)
        assignment = self._assignment(org, assignment_id) if org else None
        if not assignment or not tasks:
            return self._blocked("assignment_and_tasks_required")
        normalized = []
        for index, spec in enumerate(tasks):
            action = str(spec.get("action") or "").strip()
            if not action:
                return self._blocked("task_action_required", index=index)
            normalized.append({"id": str(spec.get("id") or f"step-{index + 1}"),
                               "action": action,
                               "depends_on": list(spec.get("depends_on") or []),
                               "input": dict(spec.get("input") or {})})
        ids = {item["id"] for item in normalized}
        for item in normalized:
            if any(dep not in ids for dep in item["depends_on"]):
                return self._blocked("dependency_reference_invalid", task=item["id"])
        graph = {item["id"]: set(item["depends_on"]) for item in normalized}
        visiting, visited = set(), set()
        def visit(node):
            if node in visiting:
                return True
            if node in visited:
                return False
            visiting.add(node)
            if any(visit(dep) for dep in graph[node]):
                return True
            visiting.remove(node)
            visited.add(node)
            return False
        if any(visit(node) for node in graph):
            return self._blocked("task_dependency_cycle_detected")
        plan = {"assignment_id": assignment.id, "organization_id": org,
                "tasks": normalized, "created_at": datetime.utcnow().isoformat(),
                "permission_snapshot": self._load(assignment.permission_snapshot_json, {})}
        assignment.plan_json = self._json(plan)
        assignment.plan_hash = self._digest(plan)
        assignment.status = "planned"
        db.session.commit()
        return {"success": True, "status": "PLANNED", "plan": plan,
                "plan_hash": assignment.plan_hash, "execution": False,
                "governance": dict(self.GOVERNANCE)}

    def create_dag_tasks(self, organization_id: int, assignment_id: int,
                         tasks: list[dict[str, Any]]) -> dict[str, Any]:
        plan_result = self.plan(organization_id, assignment_id, tasks)
        if not plan_result.get("success"):
            return plan_result
        created = []
        for spec in plan_result["plan"]["tasks"]:
            result = durable_workforce_orchestration.create_task(
                organization_id, assignment_id, spec["action"],
                input_data={"payload": spec["input"], "dag_id": spec["id"],
                            "depends_on": spec["depends_on"]},
                idempotency_key=f"dag:{plan_result['plan_hash'][:24]}:{spec['id']}",
            )
            if not result.get("success"):
                return result
            created.append(result["task"])
        return {**plan_result, "status": "DAG_CREATED", "tasks": created}

    def readiness(self, organization_id: int, task_id: int) -> dict[str, Any]:
        org = self._org(organization_id)
        row = WorkforceTask.query.filter_by(id=int(task_id), organization_id=org).first() if org else None
        if not row:
            return self._blocked("task_not_found")
        payload = self._load(row.input_json, {})
        deps = [int(value) for value in payload.get("depends_on", []) if str(value).isdigit()]
        if deps:
            dependency_rows = WorkforceTask.query.filter(WorkforceTask.organization_id == org,
                                                           WorkforceTask.id.in_(deps)).all()
            if len(dependency_rows) != len(deps):
                return self._blocked("dependency_not_found")
            blocked = [item.id for item in dependency_rows if item.state not in {"executed", "result_recorded", "measured", "learned"}]
            if blocked:
                return {"success": True, "status": "BLOCKED_BY_DEPENDENCY", "task_id": row.id,
                        "blocked_by": blocked, "execution": False}
        return {"success": True, "status": "READY", "task_id": row.id, "execution": False}

    def approval_bundle(self, organization_id: int, assignment_id: int,
                        task_ids: list[int]) -> dict[str, Any]:
        org = self._org(organization_id)
        assignment = self._assignment(org, assignment_id) if org else None
        if not assignment or not task_ids:
            return self._blocked("approval_bundle_requires_assignment_and_tasks")
        tasks = WorkforceTask.query.filter(WorkforceTask.organization_id == org,
                                           WorkforceTask.assignment_id == assignment.id,
                                           WorkforceTask.id.in_([int(x) for x in task_ids])).all()
        if len(tasks) != len(set(int(x) for x in task_ids)):
            return self._blocked("approval_bundle_task_scope_violation")
        plan_hash = str(assignment.plan_hash or "")
        if not plan_hash:
            return self._blocked("approval_bundle_requires_plan")
        payload = {"organization_id": org, "assignment_id": assignment.id,
                   "task_ids": sorted(task.id for task in tasks),
                   "plan_hash": plan_hash,
                   "permission_snapshot": self._load(assignment.permission_snapshot_json, {})}
        bundle_id = f"approval:{self._digest(payload)[:24]}"
        return {"success": True, "status": "APPROVAL_REQUIRED", "bundle_id": bundle_id,
                "approval_binding": payload, "approval_digest": self._digest(payload),
                "execution": False, "governance": dict(self.GOVERNANCE)}

    def validate_approval(self, organization_id: int, assignment_id: int,
                          approval: dict[str, Any]) -> dict[str, Any]:
        org = self._org(organization_id)
        assignment = self._assignment(org, assignment_id) if org else None
        if not assignment or not assignment.plan_hash:
            return self._blocked("assignment_plan_not_found")
        bound = approval.get("approval_binding") or {}
        if bound.get("plan_hash") != assignment.plan_hash:
            return self._blocked("approval_plan_digest_mismatch")
        current_snapshot = self._load(assignment.permission_snapshot_json, {})
        if bound.get("permission_snapshot") != current_snapshot:
            return self._blocked("approval_permission_snapshot_mismatch")
        return {"success": True, "status": "APPROVAL_VALID", "execution": False,
                "approval_digest": self._digest(bound)}

    def schedule_next(self, organization_id: int, schedule_id: int, *, now: datetime | None = None) -> dict[str, Any]:
        org = self._org(organization_id)
        row = WorkforceSchedule.query.filter_by(id=int(schedule_id), organization_id=org).first() if org else None
        if not row:
            return self._blocked("schedule_not_found")
        now = now or datetime.utcnow()
        schedule = self._load(row.schedule_json, {})
        interval = int(schedule.get("interval_seconds") or 0)
        if interval <= 0:
            return self._blocked("schedule_interval_required")
        current = row.next_run_at or now
        missed = max(0, int((now - current).total_seconds() // interval))
        next_run = current + timedelta(seconds=(missed + 1) * interval)
        schedule["last_evaluated_at"] = now.isoformat()
        schedule["missed_runs"] = missed
        schedule["next_run_key"] = f"schedule:{row.id}:{next_run.isoformat()}"
        row.schedule_json = self._json(schedule)
        row.next_run_at = next_run
        db.session.commit()
        return {"success": True, "status": "SCHEDULE_RECONCILED", "schedule": schedule,
                "next_run_at": next_run.isoformat(), "execution": False}

    def recovery_preview(self, organization_id: int, task_id: int) -> dict[str, Any]:
        result = durable_workforce_orchestration.replay_preview(organization_id, task_id)
        if not result.get("success"):
            return result
        return {**result, "resume_policy": "revalidate_dependencies_and_approval_before_canonical_execution",
                "execution": False}

    def orchestration_snapshot(self, organization_id: int) -> dict[str, Any]:
        org = self._org(organization_id)
        if not org:
            return self._blocked("organization_required")
        assignments = WorkforceAssignment.query.filter_by(organization_id=org).order_by(WorkforceAssignment.id.desc()).limit(100).all()
        tasks = WorkforceTask.query.filter_by(organization_id=org).order_by(WorkforceTask.id.desc()).limit(250).all()
        return {"success": True, "schema": self.SCHEMA, "version": self.VERSION,
                "organization_id": org,
                "assignments": [{"id": a.id, "workforce_id": a.workforce_id, "status": a.status,
                                 "parent_assignment_id": a.delegation_parent_id, "plan_hash": a.plan_hash}
                                for a in assignments],
                "tasks": [{"id": t.id, "assignment_id": t.assignment_id, "workforce_id": t.workforce_id,
                           "action": t.action, "state": t.state,
                           "dependencies": self._load(t.input_json, {}).get("depends_on", [])}
                          for t in tasks],
                "governance": dict(self.GOVERNANCE)}


governed_workforce_orchestration = GovernedWorkforceOrchestration()
