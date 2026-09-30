from app import db


class CommercialOffer(db.Model):
    __tablename__ = "commercial_offers"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("demo_leads.id"), nullable=False, index=True)
    pipeline_id = db.Column(db.Integer, db.ForeignKey("revenue_pipeline_records.id"), nullable=False, index=True)
    offer_name = db.Column(db.String(255), nullable=False)
    offer_description = db.Column(db.Text, nullable=False)
    quoted_amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(10), nullable=False, default="EGP")
    status = db.Column(db.String(30), nullable=False, default="draft", index=True)
    approval_required = db.Column(db.Boolean, nullable=False, default=True)
    evidence_provenance = db.Column(db.JSON, nullable=False, default=dict)
    approval_package_hash = db.Column(db.String(64), nullable=True, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("organization_id", "pipeline_id", name="uq_commercial_offer_org_pipeline"),
    )
