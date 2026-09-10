from datetime import datetime

from app import db


class ExecutionEvidence(db.Model):
    __tablename__ = "execution_evidence"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    execution_key = db.Column(db.String(512), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("automation_queue_jobs.id"), nullable=True, index=True)
    event_id = db.Column(db.String(255), nullable=True, index=True)
    workflow_id = db.Column(db.String(255), nullable=True, index=True)
    stage = db.Column(db.String(80), nullable=False, index=True)
    status = db.Column(db.String(40), nullable=False, index=True)
    worker_id = db.Column(db.String(255), nullable=True, index=True)
    plan_hash = db.Column(db.String(128), nullable=True, index=True)
    correlation_id = db.Column(db.String(255), nullable=True, index=True)
    trace_id = db.Column(db.String(255), nullable=True, index=True)
    evidence_key = db.Column(db.String(512), nullable=False, index=True)
    receipt_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.UniqueConstraint("organization_id", "evidence_key", name="uq_execution_evidence_org_key"),
    )
