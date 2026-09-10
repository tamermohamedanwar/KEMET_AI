from datetime import datetime

from app import db


class AutomationExecutionLedger(db.Model):
    __tablename__ = "automation_execution_ledger"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, nullable=False, index=True)
    execution_key = db.Column(db.String(512), nullable=False, index=True)
    plan_hash = db.Column(db.String(128), nullable=False, index=True)
    job_id = db.Column(db.Integer, nullable=True, index=True)
    worker_id = db.Column(db.String(255), nullable=True, index=True)
    status = db.Column(db.String(40), nullable=False, index=True)
    approval_hash = db.Column(db.String(128), nullable=True, index=True)
    trace_id = db.Column(db.String(255), nullable=True, index=True)
    correlation_id = db.Column(db.String(255), nullable=True, index=True)
    receipt_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("organization_id", "execution_key", name="uq_execution_ledger_org_key"),
    )
