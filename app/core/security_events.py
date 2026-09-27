import secrets
from datetime import datetime

from flask import has_app_context

from app import db
from app.models.security_event import SecurityEventRecord

SENSITIVE_KEYS = {
    "authorization", "cookie", "password", "passwd", "secret", "token",
    "api_key", "apikey", "access_token", "refresh_token", "private_key",
}


def _redact(value):
    if isinstance(value, dict):
        return {str(k): ("[REDACTED]" if str(k).lower() in SENSITIVE_KEYS else _redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value[:100]]
    if isinstance(value, tuple):
        return [_redact(v) for v in value[:100]]
    if isinstance(value, str) and len(value) > 4096:
        return value[:4096] + "…"
    return value


def record_security_event(event_type, *, status="recorded", severity="info", action=None,
                          actor_type="system", actor_id=None, organization_id=None,
                          correlation_id=None, metadata=None, commit=True):
    if not has_app_context():
        return None
    correlation_id = correlation_id or secrets.token_hex(16)
    previous = SecurityEventRecord.query.order_by(SecurityEventRecord.id.desc()).first()
    created_at = datetime.utcnow()
    safe_metadata = _redact(metadata or {})
    import json
    metadata_json = json.dumps(safe_metadata, ensure_ascii=False, sort_keys=True, default=str)
    previous_hash = previous.event_hash if previous else None
    event_hash = SecurityEventRecord.digest(
        correlation_id=correlation_id, event_type=event_type, actor_type=actor_type,
        actor_id=actor_id, organization_id=organization_id, action=action,
        status=status, severity=severity, metadata_json=metadata_json,
        previous_hash=previous_hash, created_at=created_at,
    )
    record = SecurityEventRecord(
        correlation_id=correlation_id, event_type=event_type, actor_type=actor_type,
        actor_id=actor_id, organization_id=organization_id, action=action,
        status=status, severity=severity, metadata_json=metadata_json,
        previous_hash=previous_hash, event_hash=event_hash, created_at=created_at,
    )
    db.session.add(record)
    if commit:
        db.session.commit()
    return record


def verify_security_event_chain(limit=None):
    query = SecurityEventRecord.query.order_by(SecurityEventRecord.id.asc())
    if limit:
        rows = query.limit(limit).all()
    else:
        rows = query.all()
    previous_hash = None
    errors = []
    for row in rows:
        if row.previous_hash != previous_hash or not row.verify_hash():
            errors.append({"id": row.id, "event_hash": row.event_hash, "error": "security_chain_integrity_failed"})
        previous_hash = row.event_hash
    return {"ok": not errors, "checked": len(rows), "errors": errors}
