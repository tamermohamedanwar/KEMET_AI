from datetime import datetime

from app import db


class MendesProductionJobRecord(db.Model):
    __tablename__ = "mendes_production_jobs"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    job_id = db.Column(db.String(255), nullable=False, unique=True, index=True)
    idempotency_key = db.Column(db.String(512), nullable=False, index=True)
    state = db.Column(db.String(40), nullable=False, index=True)
    episode_package_digest = db.Column(db.String(128), nullable=False, index=True)
    script_digest = db.Column(db.String(128), nullable=False, index=True)
    voice_contract_digest = db.Column(db.String(128), nullable=False, index=True)
    quality_gates_json = db.Column(db.Text, nullable=False)
    approval_state = db.Column(db.String(40), nullable=False)
    asset_refs_json = db.Column(db.Text, nullable=False)
    evidence_refs_json = db.Column(db.Text, nullable=False)
    job_digest = db.Column(db.String(128), nullable=False, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("organization_id", "idempotency_key", name="uq_mendes_job_org_idempotency"),
    )


class MendesProductionJobTransition(db.Model):
    __tablename__ = "mendes_production_job_transitions"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    job_id = db.Column(db.String(255), nullable=False, index=True)
    from_state = db.Column(db.String(40), nullable=False)
    to_state = db.Column(db.String(40), nullable=False)
    approval_granted = db.Column(db.Boolean, nullable=False, default=False)
    transition_digest = db.Column(db.String(128), nullable=False, index=True)
    evidence_digest = db.Column(db.String(128), nullable=True, index=True)
    metadata_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
