from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, update

from app import db
from app.models.automation_queue import AutomationQueueJob


class AutomationQueue:
    """Durable tenant queue with ownership, leases, retry caps, and deadlines."""

    VERSION = "2.0"
    DEFAULT_RETRY_DELAY = 30
    MAX_RETRY_DELAY = 3600

    def enqueue(self, envelope: dict[str, Any], *, delay_seconds: int = 0,
                deadline_seconds: int | None = None) -> dict[str, Any]:
        org_id = int(envelope["organization_id"])
        job_key = str(envelope["job_key"]).strip()
        if org_id <= 0 or not job_key:
            raise ValueError("queue_identity_required")
        existing = AutomationQueueJob.query.filter_by(
            organization_id=org_id, job_key=job_key
        ).first()
        if existing:
            return {"accepted": False, "status": "deduplicated", "job_id": existing.id}
        now = datetime.utcnow()
        deadline_at = None
        if deadline_seconds is not None:
            deadline_at = now + timedelta(seconds=max(1, int(deadline_seconds)))
        job = AutomationQueueJob(
            organization_id=org_id,
            job_key=job_key,
            event_id=envelope.get("event_id"),
            trigger_id=envelope.get("trigger_id"),
            workflow_id=envelope.get("workflow_id"),
            payload_json=json.dumps(envelope, ensure_ascii=False, default=str),
            status="queued",
            priority=int(envelope.get("priority", 100)),
            available_at=now + timedelta(seconds=max(0, int(delay_seconds))),
            max_attempts=max(1, int(envelope.get("max_attempts", 3))),
            correlation_id=envelope.get("correlation_id"),
            trace_id=envelope.get("trace_id"),
            deadline_at=deadline_at,
        )
        db.session.add(job)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            existing = AutomationQueueJob.query.filter_by(
                organization_id=org_id, job_key=job_key
            ).first()
            if existing:
                return {"accepted": False, "status": "deduplicated", "job_id": existing.id}
            raise
        return {"accepted": True, "status": "queued", "job_id": job.id}
    def claim(self, *, worker_id: str, lease_seconds: int = 60, organization_id: int | None = None) -> dict[str, Any] | None:
        worker_id = str(worker_id or "").strip()
        if not worker_id:
            raise ValueError("worker_id_required")
        now = datetime.utcnow()
        stale = AutomationQueueJob.query.filter(
            AutomationQueueJob.status == "leased",
            AutomationQueueJob.lease_until < now,
        ).all()
        for job in stale:
            job.status = "queued"
            job.lease_until = None
            job.lease_owner = None
        db.session.flush()

        filters = [AutomationQueueJob.status == "queued", AutomationQueueJob.available_at <= now]
        if organization_id is not None:
            filters.append(AutomationQueueJob.organization_id == int(organization_id))
        query = AutomationQueueJob.query.filter(*filters).order_by(
            AutomationQueueJob.priority.asc(), AutomationQueueJob.available_at.asc(),
            AutomationQueueJob.id.asc(),
        )
        if db.engine.dialect.name == "postgresql":
            job = query.with_for_update(skip_locked=True).first()
        else:
            job = query.first()
        if not job:
            db.session.commit()
            return None

        result = db.session.execute(
            update(AutomationQueueJob)
            .where(and_(AutomationQueueJob.id == job.id,
                        AutomationQueueJob.status == "queued"))
            .values(
                status="leased",
                lease_until=now + timedelta(seconds=max(1, lease_seconds)),
                lease_owner=worker_id,
                attempts=AutomationQueueJob.attempts + 1,
            )
        )
        if result.rowcount != 1:
            db.session.rollback()
            return None
        db.session.commit()
        db.session.expire_all()
        claimed = db.session.get(AutomationQueueJob, job.id)
        if claimed is None:
            return None
        return {
            "job_id": claimed.id,
            "job_key": claimed.job_key,
            "organization_id": claimed.organization_id,
            "worker_id": worker_id,
            "attempt": claimed.attempts,
            "payload": json.loads(claimed.payload_json),
            "deadline_at": claimed.deadline_at.isoformat() if claimed.deadline_at else None,
        }
    @staticmethod
    def _owned(job: AutomationQueueJob, worker_id: str | None) -> bool:
        if not job.lease_owner:
            return worker_id is None
        return bool(worker_id) and job.lease_owner == str(worker_id)

    def complete(self, job_id: int, *, worker_id: str | None = None) -> bool:
        job = db.session.get(AutomationQueueJob, int(job_id))
        if not job or job.status != "leased" or not self._owned(job, worker_id):
            return False
        job.status = "completed"
        job.lease_until = None
        job.lease_owner = None
        job.completed_at = datetime.utcnow()
        db.session.commit()
        return True

    def fail(self, job_id: int, error: str, *, worker_id: str | None = None,
             retry_delay_seconds: int = DEFAULT_RETRY_DELAY) -> dict[str, Any]:
        job = db.session.get(AutomationQueueJob, int(job_id))
        if not job:
            return {"ok": False, "status": "not_found"}
        if job.status == "leased" and not self._owned(job, worker_id):
            return {"ok": False, "status": "lease_owner_mismatch"}
        job.last_error = str(error)[:10000]
        job.lease_until = None
        job.lease_owner = None
        if job.attempts < job.max_attempts:
            job.status = "queued"
            delay = min(self.MAX_RETRY_DELAY, max(0, int(retry_delay_seconds)) * (2 ** max(0, job.attempts - 1)))
            job.available_at = datetime.utcnow() + timedelta(seconds=delay)
            status = "requeued"
        else:
            job.status = "dead_letter"
            status = "dead_letter"
        db.session.commit()
        return {"ok": True, "status": status, "attempts": job.attempts}
    def cancel(self, job_id: int, *, worker_id: str | None = None) -> bool:
        job = db.session.get(AutomationQueueJob, int(job_id))
        if not job or job.status in {"completed", "dead_letter", "cancelled"}:
            return False
        if job.status == "leased" and not self._owned(job, worker_id):
            return False
        job.status = "cancelled"
        job.lease_until = None
        job.lease_owner = None
        db.session.commit()
        return True

    def list_dead_letters(self, *, organization_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
        query = AutomationQueueJob.query.filter(AutomationQueueJob.status == "dead_letter")
        if organization_id is not None:
            query = query.filter(AutomationQueueJob.organization_id == int(organization_id))
        jobs = query.order_by(AutomationQueueJob.created_at.desc()).limit(max(1, min(int(limit), 500))).all()
        return [self._summary(job) for job in jobs]

    def requeue_dead_letter(self, job_id: int, *, worker_id: str | None = None) -> dict[str, Any]:
        job = db.session.get(AutomationQueueJob, int(job_id))
        if not job or job.status != "dead_letter":
            return {"ok": False, "status": "not_dead_letter"}
        if not worker_id:
            return {"ok": False, "status": "worker_id_required"}
        job.status = "queued"
        job.available_at = datetime.utcnow()
        job.lease_until = None
        job.lease_owner = None
        job.last_error = None
        db.session.commit()
        return {"ok": True, "status": "requeued", "job_id": job.id}

    @staticmethod
    def _summary(job: AutomationQueueJob) -> dict[str, Any]:
        return {"job_id": job.id, "job_key": job.job_key, "organization_id": job.organization_id,
                "workflow_id": job.workflow_id, "event_id": job.event_id, "attempts": job.attempts,
                "max_attempts": job.max_attempts, "last_error": job.last_error,
                "created_at": job.created_at.isoformat(), "status": job.status}

    def recover_expired(self) -> int:
        now = datetime.utcnow()
        jobs = AutomationQueueJob.query.filter(
            AutomationQueueJob.status == "leased",
            AutomationQueueJob.lease_until < now,
        ).all()
        for job in jobs:
            job.status = "queued"
            job.lease_until = None
            job.lease_owner = None
        db.session.commit()
        return len(jobs)


automation_queue = AutomationQueue()
