from app import db


class RevenuePipelineRecord(db.Model):
    __tablename__ = "revenue_pipeline_records"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    lead_id = db.Column(db.Integer, db.ForeignKey("demo_leads.id"), nullable=True, index=True)
    pipeline_key = db.Column(db.String(128), nullable=False)
    stage = db.Column(db.String(40), nullable=False, default="inquiry", index=True)
    source = db.Column(db.String(60), nullable=False, default="command_center")
    offer_name = db.Column(db.String(255), nullable=True)
    currency = db.Column(db.String(10), nullable=False, default="EGP")
    quoted_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    paid_amount = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    acquisition_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    fulfillment_cost = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    provider_fees = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    refunds = db.Column(db.Numeric(12, 2), nullable=False, default=0)
    payment_id = db.Column(db.Integer, db.ForeignKey("payments.id"), nullable=True, index=True)
    payment_transaction_id = db.Column(db.String(150), nullable=True, index=True)
    fulfillment_reference = db.Column(db.String(255), nullable=True)
    delivered_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)
    evidence_digest = db.Column(db.String(64), nullable=True, index=True)
    stage_history = db.Column(db.JSON, nullable=False, default=list)
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("organization_id", "pipeline_key", name="uq_revenue_pipeline_org_key"),
    )
