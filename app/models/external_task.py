from datetime import datetime

from app import db


class ExternalTaskRecord(db.Model):
    __tablename__ = "external_task_records"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=False, index=True)
    provider_id = db.Column(db.String(80), nullable=False, index=True)
    external_task_id = db.Column(db.String(255), nullable=False, index=True)
    execution_key = db.Column(db.String(512), nullable=False, index=True)
    plan_hash = db.Column(db.String(128), nullable=False, index=True)
    action = db.Column(db.String(255), nullable=False, index=True)
    status = db.Column(db.String(40), nullable=False, index=True)
    request_id = db.Column(db.String(255), nullable=True, index=True)
    metadata_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_seen_at = db.Column(db.DateTime, nullable=True, index=True)

    __table_args__ = (
        db.UniqueConstraint("provider_id", "external_task_id", name="uq_external_task_provider_id"),
        db.UniqueConstraint("organization_id", "execution_key", "action", name="uq_external_task_execution_action"),
    )
