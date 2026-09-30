from __future__ import annotations
from app import db

class ApiKey(db.Model):
    __tablename__ = "api_keys"
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    key_prefix = db.Column(db.String(24), nullable=False, unique=True, index=True)
    key_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    status = db.Column(db.String(20), nullable=False, default="active", index=True)
    scopes_json = db.Column(db.Text, nullable=False, default="[]")
    requests_count = db.Column(db.Integer, nullable=False, default=0)
    last_used_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)

class ApiUsageEvent(db.Model):
    __tablename__ = "api_usage_events"
    id = db.Column(db.Integer, primary_key=True)
    api_key_id = db.Column(db.Integer, db.ForeignKey("api_keys.id"), nullable=False, index=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    route = db.Column(db.String(255), nullable=False)
    status_code = db.Column(db.Integer, nullable=False)
    units = db.Column(db.Integer, nullable=False, default=1)
    request_id = db.Column(db.String(128), nullable=True, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False, index=True)
