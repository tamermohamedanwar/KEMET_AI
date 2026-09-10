from datetime import datetime

from app import db


class AutomationQueueJob(db.Model):
    __tablename__ = "automation_queue_jobs"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    job_key = db.Column(db.String(255), nullable=False, index=True)
    event_id = db.Column(db.String(255), nullable=True, index=True)
    trigger_id = db.Column(db.String(255), nullable=True, index=True)
    workflow_id = db.Column(db.String(255), nullable=True, index=True)
    payload_json = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="queued", index=True)
    priority = db.Column(db.Integer, nullable=False, default=100, index=True)
    available_at = db.Column(db.DateTime, nullable=False, index=True)
    lease_until = db.Column(db.DateTime, nullable=True)
    lease_owner = db.Column(db.String(255), nullable=True, index=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    max_attempts = db.Column(db.Integer, nullable=False, default=3)
    correlation_id = db.Column(db.String(255), nullable=True, index=True)
    trace_id = db.Column(db.String(255), nullable=True, index=True)
    deadline_at = db.Column(db.DateTime, nullable=True, index=True)
    last_error = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint("organization_id", "job_key", name="uq_automation_queue_org_job"),
    )
