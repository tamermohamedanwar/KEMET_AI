from __future__ import annotations

import json
from hashlib import sha256
from typing import Any

from app.models.automation_outcome import AutomationOutcome
from app.models.durable_workforce import WorkforceTask
from app.workforce.registry import workforce_registry
from app.workforce.runtime import workforce_runtime


class CorporateForceCardService:
    VERSION = "3.0"
    SCHEMA = "kemet.corporate_force_card.v3"

    GOVERNANCE = {
        "identity_scoped": True,
        "tenant_scoped": True,
        "role_scoped": True,
        "task_scoped": True,
        "result_scoped": True,
        "execution_authority": False,
        "external_execution": False,
        "auto_execute": False,
        "human_approval_required": True,
        "canonical_runtime_only": True,
        "fail_closed": True,
        "mcp": False,
    }

    LIFECYCLE = (
        "ASSIGNED",
        "PLANNED",
        "APPROVAL_REQUIRED",
        "EXECUTED",
        "RESULT_RECORDED",
        "MEASURED",
        "LEARNED",
    )

    @staticmethod
    def _digest(value: Any) -> str:
        canonical = json.dumps(
            value,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        return sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _require_org(organization_id: int) -> int:
        org = int(organization_id or 0)
        if org <= 0:
            raise ValueError("organization_required")
        return org

    @staticmethod
    def _task_summary(tasks: list[dict[str, Any]]) -> dict[str, Any]:
        counts = {
            "queued": 0,
            "running": 0,
            "waiting_approval": 0,
            "completed": 0,
            "failed": 0,
            "blocked": 0,
        }
        recent = []
        for task in sorted(tasks, key=lambda item: str(item.get("created_at") or ""), reverse=True):
            status = str(task.get("status") or "unknown")
            counts[status] = counts.get(status, 0) + 1
            recent.append({
                "id": task.get("id"),
                "action": task.get("action"),
                "status": status,
                "created_at": task.get("created_at"),
                "completed_at": task.get("completed_at"),
                "has_result": bool(task.get("result")),
            })
            if len(recent) >= 8:
                break
        return {"counts": counts, "recent": recent, "total": len(tasks)}

    @staticmethod
    def _result_summary(organization_id: int, workforce_id: str) -> dict[str, Any]:
        rows = (
            AutomationOutcome.query
            .filter_by(organization_id=organization_id)
            .order_by(AutomationOutcome.id.desc())
            .limit(200)
            .all()
        )
        attributed = []
        for row in rows:
            try:
                receipt = json.loads(row.receipt_json or "{}")
            except (TypeError, ValueError):
                receipt = {}
            if receipt.get("workforce_id") == workforce_id:
                attributed.append(row)

        completed = sum(1 for row in attributed if row.status == "completed")
        failed = sum(1 for row in attributed if row.status in {"failed", "error"})
        executed = sum(1 for row in attributed if row.executed)
        return {
            "source": "automation_outcomes",
            "attribution_policy": "explicit_workforce_id_only",
            "attribution_verified": bool(attributed),
            "total": len(attributed),
            "completed": completed,
            "failed": failed,
            "executed": executed,
            "success_rate": round(completed / len(attributed), 4) if attributed else None,
            "business_outcomes": sorted({
                str(row.business_outcome)
                for row in attributed
                if row.business_outcome
            }),
            "latest_outcome_id": attributed[0].id if attributed else None,
        }

    def build(self, organization_id: int, workforce_id: str) -> dict[str, Any]:
        org = self._require_org(organization_id)
        employee = workforce_registry.get(workforce_id)
        if employee is None:
            return {
                "schema": self.SCHEMA,
                "version": self.VERSION,
                "status": "BLOCKED",
                "error": "workforce_not_found",
                "organization_id": org,
                "governance": dict(self.GOVERNANCE),
            }

        task_list = [
            task for task in workforce_runtime.list_tasks(org)
            if str(task.get("workforce_id")) == str(workforce_id)
        ]
        task_summary = self._task_summary(task_list)
        durable_rows = (WorkforceTask.query.filter_by(organization_id=org, workforce_id=str(workforce_id))
                        .order_by(WorkforceTask.id.desc()).limit(200).all())
        durable_counts = {}
        for row in durable_rows:
            durable_counts[row.state] = durable_counts.get(row.state, 0) + 1
        task_summary["durable"] = {
            "total": len(durable_rows),
            "states": durable_counts,
            "persistent": True,
            "history": True,
        }
        result_summary = self._result_summary(org, str(workforce_id))
        expected_metrics = list(employee.get("metrics", []))
        allowed_actions = list(employee.get("allowed_actions", []))
        approval_actions = list(employee.get("approval_actions", []))

        payload = {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "organization_id": org,
            "identity": {
                "id": str(workforce_id),
                "name": employee.get("name", workforce_id),
                "status": "ready",
                "description": employee.get("description", ""),
            },
            "role": {
                "name": employee.get("role", ""),
                "industries": list(employee.get("industries", [])),
                "capabilities": list(employee.get("capabilities", [])),
                "allowed_actions": allowed_actions,
                "approval_actions": approval_actions,
                "authority": "proposal_only",
            },
            "tasks": {
                "assignment_contract": {
                    "accepted_actions": sorted(set(allowed_actions + approval_actions)),
                    "approval_required_for": approval_actions,
                    "unknown_actions": "BLOCKED",
                },
                "state": task_summary,
            },
            "results": {
                "expected_metrics": expected_metrics,
                "observed": result_summary,
                "evidence_required": True,
                "causal_claim": False,
                "revenue_claim": "only_with_authoritative_evidence",
            },
            "lifecycle": list(self.LIFECYCLE),
            "governance": dict(self.GOVERNANCE),
        }
        return {
            **payload,
            "card_digest": self._digest(payload),
        }

    def build_team(self, organization_id: int) -> dict[str, Any]:
        org = self._require_org(organization_id)
        cards = [
            self.build(org, profile["id"])
            for profile in workforce_registry.list()
        ]
        ready = [card for card in cards if card.get("status") != "BLOCKED"]
        payload = {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "organization_id": org,
            "cards": cards,
            "card_count": len(cards),
            "ready_count": len(ready),
            "governance": dict(self.GOVERNANCE),
        }
        return {**payload, "team_digest": self._digest(payload)}


corporate_force_card = CorporateForceCardService()
