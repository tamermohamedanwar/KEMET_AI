import hashlib
import json
from datetime import datetime

from app import db


class SecurityEventRecord(db.Model):
    __tablename__ = "security_event_records"

    id = db.Column(db.Integer, primary_key=True)
    correlation_id = db.Column(db.String(128), nullable=False, index=True)
    event_type = db.Column(db.String(120), nullable=False, index=True)
    actor_type = db.Column(db.String(40), nullable=False, default="system")
    actor_id = db.Column(db.String(160), nullable=True, index=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    action = db.Column(db.String(160), nullable=True, index=True)
    status = db.Column(db.String(50), nullable=False, index=True)
    severity = db.Column(db.String(20), nullable=False, default="info", index=True)
    metadata_json = db.Column(db.Text, nullable=False, default="{}")
    previous_hash = db.Column(db.String(64), nullable=True)
    event_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    def set_metadata(self, metadata):
        self.metadata_json = json.dumps(metadata or {}, ensure_ascii=False, sort_keys=True, default=str)

    def get_metadata(self):
        try:
            return json.loads(self.metadata_json or "{}")
        except (TypeError, ValueError):
            return {}

    @staticmethod
    def digest(*, correlation_id, event_type, actor_type, actor_id, organization_id,
               action, status, severity, metadata_json, previous_hash, created_at):
        payload = {
            "correlation_id": correlation_id,
            "event_type": event_type,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "organization_id": organization_id,
            "action": action,
            "status": status,
            "severity": severity,
            "metadata_json": metadata_json,
            "previous_hash": previous_hash,
            "created_at": created_at.isoformat(),
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def verify_hash(self):
        return self.event_hash == self.digest(
            correlation_id=self.correlation_id,
            event_type=self.event_type,
            actor_type=self.actor_type,
            actor_id=self.actor_id,
            organization_id=self.organization_id,
            action=self.action,
            status=self.status,
            severity=self.severity,
            metadata_json=self.metadata_json,
            previous_hash=self.previous_hash,
            created_at=self.created_at,
        )
