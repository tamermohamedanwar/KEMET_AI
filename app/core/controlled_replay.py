from __future__ import annotations

from typing import Any

from app.core.automation_queue import AutomationQueue, automation_queue
from app.core.execution.authorization import execution_authorization


class ControlledReplayService:
    VERSION = "1.0"

    def __init__(self, queue: AutomationQueue | None = None) -> None:
        self.queue = queue or automation_queue

    def replay(self, *, job_id: int, authorization: dict[str, Any], approver_id: int | None = None) -> dict[str, Any]:
        if not isinstance(authorization, dict):
            return {"ok": False, "status": "fresh_authorization_required"}
        token = str(authorization.get("token") or "")
        if not token:
            return {"ok": False, "status": "fresh_authorization_required"}
        job = self._get_dead_letter(job_id)
        if job is None:
            return {"ok": False, "status": "not_dead_letter"}
        if authorization.get("one_time") is not True:
            return {"ok": False, "status": "fresh_authorization_required"}
        payload = __import__("json").loads(job.payload_json or "{}")
        replay_plan = payload.get("plan") or payload.get("execution_plan")
        replay_action = payload.get("action") or (replay_plan or {}).get("action")
        if not isinstance(replay_plan, dict) or not replay_action:
            return {"ok": False, "status": "replay_plan_context_missing"}
        verified = execution_authorization.verify(authorization, replay_plan, str(replay_action))
        if not verified.get("authorized"):
            return {"ok": False, "status": "authorization_rejected", "detail": verified}
        authorization = dict(authorization)
        if approver_id is not None:
            authorization["approver_id"] = approver_id
        consumed = execution_authorization.consume(authorization)
        if not consumed:
            return {"ok": False, "status": "authorization_rejected"}
        result = self.queue.requeue_dead_letter(job_id, worker_id=f"replay:{approver_id or 'authorized'}")
        if not result.get("ok"):
            return result
        return {"ok": True, "status": "requeued_with_fresh_authorization", "job_id": job_id}

    @staticmethod
    def _get_dead_letter(job_id: int):
        from app import db
        from app.models.automation_queue import AutomationQueueJob
        job = db.session.get(AutomationQueueJob, int(job_id))
        return job if job and job.status == "dead_letter" else None


controlled_replay = ControlledReplayService()
