from datetime import datetime

from app import db


class AutomationOutcome(db.Model):
    __tablename__ = "automation_outcomes"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("automation_queue_jobs.id"), nullable=True, index=True)
    workflow_id = db.Column(db.String(255), nullable=True, index=True)
    event_id = db.Column(db.String(255), nullable=True, index=True)
    status = db.Column(db.String(40), nullable=False, index=True)
    executed = db.Column(db.Boolean, nullable=False, default=False)
    duration_ms = db.Column(db.Integer, nullable=True)
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    cost_amount = db.Column(db.Numeric(18, 6), nullable=True)
    currency = db.Column(db.String(10), nullable=True)
    business_outcome = db.Column(db.String(100), nullable=True)
    correlation_id = db.Column(db.String(255), nullable=True, index=True)
    trace_id = db.Column(db.String(255), nullable=True, index=True)
    receipt_json = db.Column(db.Text, nullable=True)
    error_type = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
