from __future__ import annotations

import json
from datetime import datetime

from app import db


class AuditRecord(db.Model):
    __tablename__ = "audit_records"

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(100), nullable=False, index=True)
    actor_type = db.Column(db.String(30), nullable=False, default="system")
    actor_id = db.Column(db.String(100), nullable=True, index=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    action = db.Column(db.String(100), nullable=True, index=True)
    status = db.Column(db.String(50), nullable=False, default="recorded", index=True)
    metadata_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def set_metadata(self, metadata):
        self.metadata_json = json.dumps(
            metadata or {},
            ensure_ascii=False,
            default=str,
        )

    def get_metadata(self):
        try:
            return json.loads(self.metadata_json or "{}")
        except (TypeError, ValueError):
            return {}
