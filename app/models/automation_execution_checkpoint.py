from datetime import datetime

from app import db


class AutomationExecutionCheckpoint(db.Model):
    __tablename__ = "automation_execution_checkpoints"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=False, index=True)
    execution_key = db.Column(db.String(512), nullable=False, index=True)
    plan_hash = db.Column(db.String(128), nullable=False, index=True)
    step_id = db.Column(db.String(255), nullable=False)
    ordinal = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(40), nullable=False, index=True)
    attempt = db.Column(db.Integer, nullable=False, default=1)
    worker_id = db.Column(db.String(255), nullable=True, index=True)
    result_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id", "execution_key", "step_id",
            name="uq_execution_checkpoint_org_key_step",
        ),
    )
