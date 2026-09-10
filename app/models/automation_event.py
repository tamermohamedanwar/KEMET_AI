from datetime import datetime

from app import db


class AutomationEventRecord(db.Model):
    __tablename__ = "automation_event_records"
    __table_args__ = (
        db.UniqueConstraint(
            "organization_id", "source", "idempotency_key",
            name="uq_automation_event_org_source_idem",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    event_id = db.Column(db.String(255), nullable=False, index=True)
    event_type = db.Column(db.String(150), nullable=False, index=True)
    source = db.Column(db.String(100), nullable=False, default="internal")
    idempotency_key = db.Column(db.String(255), nullable=False, index=True)
    correlation_id = db.Column(db.String(255), nullable=True, index=True)
    trace_id = db.Column(db.String(255), nullable=True, index=True)
    payload_json = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(30), nullable=False, default="accepted", index=True)
    attempts = db.Column(db.Integer, nullable=False, default=0)
    occurred_at = db.Column(db.DateTime, nullable=False)
    received_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f"<AutomationEventRecord {self.id} {self.event_type} {self.status}>"
