from datetime import datetime

from app import db


class MLEvaluationRecord(db.Model):
    __tablename__ = "ml_evaluation_records"
    __table_args__ = (
        db.UniqueConstraint("organization_id", "evaluation_key", name="uq_ml_eval_org_key"),
        db.Index("ix_ml_eval_org_status", "organization_id", "status"),
        db.Index("ix_ml_eval_org_dataset", "organization_id", "dataset_sha256"),
    )

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    evaluation_key = db.Column(db.String(255), nullable=False)
    task_id = db.Column(db.String(255), nullable=False, index=True)
    dataset_id = db.Column(db.String(255), nullable=False, index=True)
    dataset_sha256 = db.Column(db.String(64), nullable=False, index=True)
    authorization_reference = db.Column(db.String(255), nullable=False, index=True)
    authorization_digest = db.Column(db.String(64), nullable=False)
    intake_digest = db.Column(db.String(64), nullable=True)
    evaluation_digest = db.Column(db.String(64), nullable=False)
    evidence_digest = db.Column(db.String(64), nullable=True)
    evidence_completion_digest = db.Column(db.String(64), nullable=True)
    status = db.Column(db.String(64), nullable=False, default="review_required", index=True)
    approval_status = db.Column(db.String(32), nullable=False, default="pending")
    execution_status = db.Column(db.String(32), nullable=False, default="not_executed")
    payload_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
