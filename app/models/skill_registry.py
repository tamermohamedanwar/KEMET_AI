from datetime import datetime

from app import db


class SkillVersionRecord(db.Model):
    __tablename__ = "skill_version_records"

    id = db.Column(db.Integer, primary_key=True)
    skill_id = db.Column(db.String(160), nullable=False, index=True)
    version = db.Column(db.String(80), nullable=False)
    digest = db.Column(db.String(64), nullable=False, index=True)
    manifest_json = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(32), nullable=False, index=True)
    active = db.Column(db.Boolean, nullable=False, default=False, index=True)
    approved_by = db.Column(db.String(160), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    published_at = db.Column(db.DateTime, nullable=True)
    retired_at = db.Column(db.DateTime, nullable=True)
    admission_version = db.Column(db.String(32), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("skill_id", "version", name="uq_skill_version_identity"),
    )
