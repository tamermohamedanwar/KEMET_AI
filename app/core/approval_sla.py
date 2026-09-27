from __future__ import annotations

from datetime import datetime, timedelta


DEFAULT_SLA_SECONDS = {
    "critical": 300,
    "high": 900,
    "medium": 1800,
    "low": 3600,
}


def risk_level(action: str, reason: str = "") -> str:
    text = f"{action} {reason}".lower()
    if any(x in text for x in ("delete", "refund", "payment", "permission", "credential")):
        return "critical"
    if any(x in text for x in ("send", "publish", "external", "execute", "database")):
        return "high"
    if any(x in text for x in ("write", "update", "create", "notify", "assign")):
        return "medium"
    return "low"


def deadline_for(created_at: datetime, level: str) -> datetime:
    return created_at + timedelta(seconds=DEFAULT_SLA_SECONDS.get(level, 1800))


def approval_state(created_at: datetime, action: str, reason: str = "", now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    level = risk_level(action, reason)
    deadline = deadline_for(created_at, level)
    expired = now >= deadline
    return {
        "risk": level,
        "sla_seconds": DEFAULT_SLA_SECONDS[level],
        "deadline_at": deadline.isoformat() + "Z",
        "expired": expired,
        "default_on_timeout": "deny",
    }
