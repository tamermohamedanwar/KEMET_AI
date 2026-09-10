from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Any

from app import db
from app.models.automation_schedule import AutomationSchedule
from app.core.automation_scheduler import automation_scheduler


class AutomationScheduleService:
    VERSION = "1.0"

    @staticmethod
    def _tz(name: str) -> ZoneInfo:
        try:
            return ZoneInfo(name or "UTC")
        except ZoneInfoNotFoundError as exc:
            raise ValueError("invalid_timezone") from exc

    def create(self, *, organization_id: int, schedule_key: str, workflow_id: str,
               interval_seconds: int, timezone_name: str = "UTC",
               first_run_at: datetime | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        if organization_id <= 0 or not schedule_key.strip() or not workflow_id.strip():
            raise ValueError("schedule_identity_required")
        if interval_seconds < 1:
            raise ValueError("interval_seconds_required")
        self._tz(timezone_name)
        now = datetime.utcnow()
        first = first_run_at or now
        if first.tzinfo is not None:
            first = first.astimezone(timezone.utc).replace(tzinfo=None)
        schedule = AutomationSchedule(
            organization_id=organization_id,
            schedule_key=schedule_key.strip(),
            workflow_id=workflow_id.strip(),
            interval_seconds=interval_seconds,
            timezone=timezone_name,
            next_run_at=first,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False, default=str),
        )
        db.session.add(schedule)
        db.session.commit()
        return self.as_dict(schedule)

    def due(self, *, organization_id: int, now: datetime | None = None) -> list[AutomationSchedule]:
        current = now or datetime.utcnow()
        return AutomationSchedule.query.filter(
            AutomationSchedule.organization_id == organization_id,
            AutomationSchedule.enabled.is_(True),
            AutomationSchedule.next_run_at <= current,
        ).order_by(AutomationSchedule.next_run_at.asc()).all()

    def enqueue_due(self, *, organization_id: int, now: datetime | None = None) -> list[dict[str, Any]]:
        current = now or datetime.utcnow()
        results = []
        for schedule in self.due(organization_id=organization_id, now=current):
            event_id = f"schedule:{schedule.id}:{schedule.next_run_at.isoformat()}"
            intent = {
                "organization_id": organization_id,
                "event_id": event_id,
                "trigger_id": f"schedule:{schedule.schedule_key}",
                "workflow_id": schedule.workflow_id,
                "priority": 100,
                "execution": {"approval_required": True},
            }
            queued = automation_scheduler.enqueue_intent(intent)
            schedule.last_run_at = schedule.next_run_at
            schedule.next_run_at = schedule.next_run_at + timedelta(seconds=schedule.interval_seconds)
            schedule.run_count += 1
            db.session.commit()
            results.append({"schedule_id": schedule.id, "queue": queued})
        return results

    @staticmethod
    def as_dict(schedule: AutomationSchedule) -> dict[str, Any]:
        return {
            "id": schedule.id,
            "organization_id": schedule.organization_id,
            "schedule_key": schedule.schedule_key,
            "workflow_id": schedule.workflow_id,
            "interval_seconds": schedule.interval_seconds,
            "timezone": schedule.timezone,
            "enabled": schedule.enabled,
            "next_run_at": schedule.next_run_at.isoformat(),
            "last_run_at": schedule.last_run_at.isoformat() if schedule.last_run_at else None,
            "run_count": schedule.run_count,
        }


automation_schedule_service = AutomationScheduleService()
