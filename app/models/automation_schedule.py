from datetime import datetime

from app import db


class AutomationSchedule(db.Model):
    __tablename__ = "automation_schedules"
    __table_args__ = (
        db.UniqueConstraint("organization_id", "schedule_key", name="uq_automation_schedule_org_key"),
    )

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    schedule_key = db.Column(db.String(255), nullable=False)
    workflow_id = db.Column(db.String(255), nullable=False, index=True)
    interval_seconds = db.Column(db.Integer, nullable=False)
    timezone = db.Column(db.String(100), nullable=False, default="UTC")
    enabled = db.Column(db.Boolean, nullable=False, default=True, index=True)
    next_run_at = db.Column(db.DateTime, nullable=False, index=True)
    last_run_at = db.Column(db.DateTime, nullable=True)
    run_count = db.Column(db.Integer, nullable=False, default=0)
    metadata_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<AutomationSchedule {self.id} {self.schedule_key}>"
