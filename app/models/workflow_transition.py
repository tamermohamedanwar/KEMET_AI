from datetime import datetime

from app import db


class WorkflowTransitionRecord(db.Model):
    __tablename__ = "workflow_transition_records"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    job_id = db.Column(db.String(255), nullable=False, index=True)
    workflow_id = db.Column(db.String(255), nullable=False, index=True)
    execution_id = db.Column(db.String(255), nullable=False, index=True)
    idempotency_key = db.Column(db.String(255), nullable=False, index=True)
    from_state = db.Column(db.String(40), nullable=False)
    to_state = db.Column(db.String(40), nullable=False)
    reason = db.Column(db.String(500), nullable=True)
    actor = db.Column(db.String(255), nullable=True)
    plan_hash = db.Column(db.String(128), nullable=True, index=True)
    decision_hash = db.Column(db.String(128), nullable=True, index=True)
    approval_id = db.Column(db.String(255), nullable=True, index=True)
    execution_key = db.Column(db.String(255), nullable=True, index=True)
    metadata_digest = db.Column(db.String(64), nullable=True)
    metadata_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.Index("ix_workflow_transition_identity", "organization_id", "job_id", "created_at"),
    )
