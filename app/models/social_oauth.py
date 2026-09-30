from datetime import datetime

from app import db


class SocialOAuthState(db.Model):
    __tablename__ = "social_oauth_states"

    id = db.Column(db.Integer, primary_key=True)
    state_digest = db.Column(db.String(64), nullable=False, unique=True, index=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    channel = db.Column(db.String(64), nullable=False, index=True)
    purpose = db.Column(db.String(64), nullable=False, default="content_publishing")
    expires_at = db.Column(db.DateTime, nullable=False, index=True)
    consumed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class EncryptedSocialCredential(db.Model):
    __tablename__ = "encrypted_social_credentials"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    channel = db.Column(db.String(64), nullable=False, index=True)
    credential_ref = db.Column(db.String(128), nullable=False, unique=True, index=True)
    ciphertext = db.Column(db.Text, nullable=False)
    key_version = db.Column(db.String(32), nullable=False, default="v1")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("organization_id", "user_id", "channel", name="uq_social_credential_scope"),
    )
