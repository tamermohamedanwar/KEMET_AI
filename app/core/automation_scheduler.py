from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from app.core.automation_queue import automation_queue
from app.core.workflow_runtime import WorkflowState


class AutomationScheduler:
    """Build queue-ready envelopes without executing business actions."""

    VERSION = "1.0"

    @staticmethod
    def _job_key(organization_id: int, event_id: str, trigger_id: str) -> str:
        raw = f"{organization_id}:{event_id}:{trigger_id}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def envelope(self, intent: dict[str, Any], *, correlation_id: str | None = None,
                 trace_id: str | None = None, max_attempts: int = 3,
                 deadline_seconds: int = 300) -> dict[str, Any]:
        org_id = int(intent["organization_id"])
        event_id = str(intent["event_id"])
        trigger_id = str(intent["trigger_id"])
        return {
            "schema": "kemet.automation.envelope.v1",
            "job_key": self._job_key(org_id, event_id, trigger_id),
            "organization_id": org_id,
            "event_id": event_id,
            "trigger_id": trigger_id,
            "workflow_id": intent["workflow_id"],
            "execution_id": intent.get("execution_id"),
            "idempotency_key": intent.get("idempotency_key") or AutomationScheduler._job_key(org_id, event_id, trigger_id),
            "workflow_state": intent.get("workflow_state") or (WorkflowState.WAITING_APPROVAL if intent.get("execution", {}).get("approval_required") else WorkflowState.QUEUED),
            "priority": int(intent.get("priority", 100)),
            "correlation_id": correlation_id,
            "trace_id": trace_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "max_attempts": max(1, int(max_attempts)),
            "deadline_seconds": max(1, int(deadline_seconds)),
            "execution": {
                "executed": False,
                "external_execution": False,
                "database_mutation": False,
                "approval_required": bool(intent.get("execution", {}).get("approval_required")),
            },
        }

    def enqueue_intent(self, intent: dict[str, Any], *, correlation_id: str | None = None,
                       trace_id: str | None = None, delay_seconds: int = 0,
                       deadline_seconds: int = 300) -> dict[str, Any]:
        envelope = self.envelope(intent, correlation_id=correlation_id, trace_id=trace_id,
                                 deadline_seconds=deadline_seconds)
        queued = automation_queue.enqueue(envelope, delay_seconds=delay_seconds,
                                          deadline_seconds=deadline_seconds)
        return {"envelope": envelope, "queue": queued, "scheduler": self.VERSION}


automation_scheduler = AutomationScheduler()
