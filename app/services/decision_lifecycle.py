from datetime import datetime
import json

from app.models.automation import AutomationApproval, AutomationExecution
from app.models.user import User
from app.services.capability_registry import capability_registry
from app.services.outcome_intelligence import outcome_intelligence


class DecisionLifecycleService:
    """Read-only lifecycle projection for governed BOS decisions."""

    VERSION = "1.1"
    STATES = (
        "detected",
        "ranked",
        "reviewed",
        "approved",
        "rejected",
        "executed",
        "outcome_observed",
    )

    @classmethod
    def _decision_key(cls, decision):
        return str(decision.get("decision_id") or decision.get("id") or "").strip()

    @classmethod
    def _capability_id(cls, decision):
        action = str(decision.get("action") or decision.get("executable_action") or "").strip()
        if not action:
            return None
        capability = capability_registry.get(f"kemet.{action}")
        return f"kemet.{action}" if capability else None

    @classmethod
    def _approval_records(cls, organization_id, decision_id):
        records = AutomationApproval.query.filter_by(
            organization_id=organization_id,
        ).order_by(AutomationApproval.created_at.desc()).all()
        matched = []
        for record in records:
            payload = {}
            try:
                payload = json.loads(record.request_json or "{}")
            except Exception:
                payload = {}
            data = payload.get("data") if isinstance(payload, dict) else {}
            if isinstance(data, dict) and str(data.get("decision_id") or "") == decision_id:
                matched.append(record)
        return matched

    @classmethod
    def _execution_records(cls, organization_id, approvals):
        ids = {record.execution_id for record in approvals if record.execution_id}
        if not ids:
            return []
        rows = AutomationExecution.query.filter(
            AutomationExecution.id.in_(ids)
        ).all()
        allowed = []
        for row in rows:
            workflow = getattr(row, "workflow", None)
            if workflow and workflow.organization_id == organization_id:
                allowed.append(row)
        return sorted(allowed, key=lambda item: item.created_at or datetime.min, reverse=True)

    @classmethod
    def _history(cls, decision, approvals, executions, impact):
        events = []
        detected_at = decision.get("detected_at") or decision.get("created_at") or decision.get("generated_at")
        if detected_at:
            events.append({"state": "detected", "at": str(detected_at), "source": "decision"})
        if decision.get("outcome_priority_score") is not None:
            events.append({"state": "ranked", "at": str(decision.get("ranked_at") or detected_at or ""), "source": "outcome_priority"})
        for approval in approvals:
            created = approval.created_at.isoformat() if approval.created_at else None
            decided = approval.decided_at.isoformat() if approval.decided_at else None
            events.append({"state": "reviewed", "at": created, "source": "approval", "approval_id": approval.id})
            status = str(approval.status or "").lower()
            if status in {"approved", "rejected", "denied"}:
                state = "approved" if status == "approved" else "rejected"
                events.append({"state": state, "at": decided or created, "source": "approval", "approval_id": approval.id})
        for execution in executions:
            at = execution.completed_at or execution.started_at or execution.created_at
            status = str(execution.status or "").lower()
            events.append({"state": "executed", "at": at.isoformat() if at else None, "source": "execution", "execution_id": execution.id, "status": status})
        if impact and impact.get("success") and impact.get("observed_impact"):
            events.append({"state": "outcome_observed", "at": impact.get("generated_at"), "source": "outcome_intelligence"})
        return sorted(events, key=lambda item: str(item.get("at") or ""))

    @classmethod
    def _accountability(cls, organization_id, approvals, executions):
        user_ids = {
            record.requested_by for record in approvals if record.requested_by
        } | {
            record.decided_by for record in approvals if record.decided_by
        }
        users = {}
        if user_ids:
            rows = User.query.filter(
                User.organization_id == organization_id,
                User.id.in_(user_ids),
            ).all()
            users = {row.id: row for row in rows}

        approval_rows = []
        for approval in approvals:
            requester = users.get(approval.requested_by)
            decider = users.get(approval.decided_by)
            approval_rows.append({
                "approval_id": approval.id,
                "status": approval.status,
                "requested_at": approval.created_at.isoformat() if approval.created_at else None,
                "requested_by": {
                    "user_id": requester.id,
                    "name": requester.full_name,
                    "role": requester.role,
                } if requester else None,
                "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
                "decided_by": {
                    "user_id": decider.id,
                    "name": decider.full_name,
                    "role": decider.role,
                } if decider else None,
                "reason": approval.reason,
            })

        execution_rows = []
        for execution in executions:
            execution_rows.append({
                "execution_id": execution.id,
                "status": execution.status,
                "started_at": execution.started_at.isoformat() if execution.started_at else None,
                "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
                "error": execution.error_message,
                "workflow_id": execution.workflow_id,
            })

        return {
            "approvals": approval_rows,
            "executions": execution_rows,
            "reviewed_by": next((item["decided_by"] for item in approval_rows if item["decided_by"]), None),
            "governance": {
                "read_only": True,
                "advisory": True,
                "no_new_audit_record": True,
                "external_execution": False,
                "database_mutation": False,
            },
        }

    @classmethod
    def _state(cls, decision, approvals, executions, impact):
        if executions and any(str(row.status).lower() == "completed" for row in executions):
            if impact and impact.get("success") and impact.get("observed_impact"):
                return "outcome_observed"
            return "executed"
        if any(str(row.status).lower() == "failed" for row in executions):
            return "executed"
        if approvals:
            latest = approvals[0]
            status = str(latest.status or "").lower()
            if status in {"approved", "executed"}:
                return "approved"
            if status in {"rejected", "denied"}:
                return "rejected"
            if status in {"pending", "waiting_approval"}:
                return "reviewed"
        if decision.get("outcome_priority_score") is not None:
            return "ranked"
        return "detected"

    @classmethod
    def build(cls, organization_id, decision, period="30d"):
        if not organization_id:
            return {"success": False, "error": "organization_required"}
        if not isinstance(decision, dict):
            return {"success": False, "error": "decision_required"}

        decision_id = cls._decision_key(decision)
        if not decision_id:
            return {"success": False, "error": "decision_id_required"}

        capability_id = cls._capability_id(decision)
        approvals = cls._approval_records(organization_id, decision_id)
        executions = cls._execution_records(organization_id, approvals)

        impact = None
        if capability_id:
            try:
                impact = outcome_intelligence.build(organization_id, capability_id, period)
            except Exception:
                impact = None

        state = cls._state(decision, approvals, executions, impact)
        timeline = [
            {"state": "detected", "label": "Detected", "complete": True},
            {"state": "ranked", "label": "Ranked", "complete": state in cls.STATES[1:]},
            {"state": "reviewed", "label": "Reviewed", "complete": state in cls.STATES[2:]},
            {"state": "approved", "label": "Approved", "complete": state in {"approved", "executed", "outcome_observed"}},
            {"state": "executed", "label": "Executed", "complete": state in {"executed", "outcome_observed"}},
            {"state": "outcome_observed", "label": "Outcome Observed", "complete": state == "outcome_observed"},
        ]
        if state == "rejected":
            timeline[3] = {"state": "rejected", "label": "Rejected", "complete": True}

        latest_approval = approvals[0] if approvals else None
        latest_execution = executions[0] if executions else None
        outcome_receipt = None
        if latest_execution and latest_execution.output_json:
            try:
                checkpoint = json.loads(latest_execution.output_json or "{}")
                if isinstance(checkpoint, dict) and isinstance(checkpoint.get("outcome"), dict):
                    outcome_receipt = checkpoint.get("outcome")
            except Exception:
                outcome_receipt = None
        history = cls._history(decision, approvals, executions, impact)
        accountability = cls._accountability(organization_id, approvals, executions)

        return {
            "success": True,
            "version": cls.VERSION,
            "organization_id": organization_id,
            "decision_id": decision_id,
            "capability_id": capability_id,
            "state": state,
            "timeline": timeline,
            "history": history,
            "history_count": len(history),
            "accountability": accountability,
            "approval": {
                "id": latest_approval.id if latest_approval else None,
                "status": latest_approval.status if latest_approval else None,
                "requested_by": latest_approval.requested_by if latest_approval else None,
                "decided_by": latest_approval.decided_by if latest_approval else None,
                "requested_at": latest_approval.created_at.isoformat() if latest_approval and latest_approval.created_at else None,
                "decided_at": latest_approval.decided_at.isoformat() if latest_approval and latest_approval.decided_at else None,
                "reason": latest_approval.reason if latest_approval else None,
            },
            "execution": {
                "id": latest_execution.id if latest_execution else None,
                "status": latest_execution.status if latest_execution else None,
            },
            "observed_outcome": (
                (outcome_receipt or {}).get("observed", {}).get("deltas", {})
                if outcome_receipt else (impact or {}).get("observed_impact", [])
            ),
            "outcome_receipt": outcome_receipt,
            "governance": {
                "read_only": True,
                "advisory": True,
                "causal_claim": False,
                "roi_claim": False,
                "external_execution": False,
                "database_mutation": False,
            },
        }

    @classmethod
    def project(cls, organization_id, decisions, period="30d"):
        if not organization_id:
            return {"success": False, "error": "organization_required", "items": []}
        items = []
        for decision in decisions or []:
            result = cls.build(organization_id, decision, period)
            if result.get("success"):
                items.append(result)
        return {
            "success": True,
            "version": cls.VERSION,
            "organization_id": organization_id,
            "items": items,
            "count": len(items),
            "governance": {
                "read_only": True,
                "advisory": True,
                "external_execution": False,
                "database_mutation": False,
            },
        }
