from datetime import datetime

from app import db


class LeadIntelligenceEvidence(db.Model):
    __tablename__ = "lead_intelligence_evidence"

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("demo_leads.id"), nullable=False, index=True)
    operation = db.Column(db.String(60), nullable=False, index=True)
    before_digest = db.Column(db.String(64), nullable=True)
    after_digest = db.Column(db.String(64), nullable=False)
    evidence_digest = db.Column(db.String(64), nullable=False, index=True)
    evidence_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)

    __table_args__ = (
        db.UniqueConstraint(
            "tenant_id",
            "lead_id",
            "operation",
            "after_digest",
            name="uq_lead_intelligence_evidence_step",
        ),
    )
