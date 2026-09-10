from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from app import db
from app.models.automation_queue import AutomationQueueJob
from app.core.automation_queue import AutomationQueue, automation_queue


@dataclass(frozen=True)
class WorkerAdmission:
    allowed: bool
    reason: str
    organization_active: int = 0
    global_active: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {"allowed": self.allowed, "reason": self.reason,
                "organization_active": self.organization_active,
                "global_active": self.global_active}


class WorkerCoordinator:
    """Coordinates worker admission, heartbeats, cancellation and recovery."""

    VERSION = "1.1"
    DEFAULT_ORG_LIMIT = 5
    DEFAULT_GLOBAL_LIMIT = 50

    def __init__(self, queue: AutomationQueue | None = None) -> None:
        self.queue = queue or automation_queue

    def admit(self, *, organization_id: int, current_job_id: int | None = None,
              org_limit: int = DEFAULT_ORG_LIMIT,
              global_limit: int = DEFAULT_GLOBAL_LIMIT) -> dict[str, Any]:
        org_query = AutomationQueueJob.query.filter(
            AutomationQueueJob.organization_id == organization_id,
            AutomationQueueJob.status == "leased",
        )
        global_query = AutomationQueueJob.query.filter(AutomationQueueJob.status == "leased")
        if current_job_id is not None:
            org_query = org_query.filter(AutomationQueueJob.id != current_job_id)
            global_query = global_query.filter(AutomationQueueJob.id != current_job_id)
        org_active = org_query.count()
        global_active = global_query.count()
        if org_active >= max(1, org_limit):
            return WorkerAdmission(False, "organization_concurrency_limit", org_active, global_active).as_dict()
        if global_active >= max(1, global_limit):
            return WorkerAdmission(False, "global_concurrency_limit", org_active, global_active).as_dict()
        return WorkerAdmission(True, "admitted", org_active, global_active).as_dict()

    def heartbeat(self, *, job_id: int, worker_id: str, lease_seconds: int = 60) -> bool:
        job = db.session.get(AutomationQueueJob, int(job_id))
        if not job or job.status != "leased" or job.lease_owner != str(worker_id):
            return False
        job.lease_until = datetime.utcnow() + timedelta(seconds=max(1, lease_seconds))
        db.session.commit()
        return True

    def request_cancel(self, *, job_id: int, requester: str) -> bool:
        job = db.session.get(AutomationQueueJob, int(job_id))
        if not job or job.status not in {"queued", "leased"}:
            return False
        job.status = "cancellation_requested"
        job.last_error = f"cancellation_requested:{str(requester)[:120]}"
        db.session.commit()
        return True

    def is_cancelled(self, *, job_id: int, worker_id: str | None = None) -> bool:
        try:
            job = db.session.get(AutomationQueueJob, int(job_id))
        except RuntimeError:
            return False
        if not job:
            return True
        if worker_id and job.lease_owner and job.lease_owner != str(worker_id):
            return True
        return job.status == "cancellation_requested"

    def recover(self) -> dict[str, int]:
        return {"expired_leases_recovered": self.queue.recover_expired()}


worker_coordinator = WorkerCoordinator()
