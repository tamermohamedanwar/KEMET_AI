from app import db


class ProviderConnectionRecord(db.Model):
    __tablename__ = "provider_connection_records"

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    provider_id = db.Column(db.String(64), nullable=False, index=True)
    mode = db.Column(db.String(32), nullable=False)
    status = db.Column(db.String(32), nullable=False, index=True)
    scopes_json = db.Column(db.JSON, nullable=False, default=list)
    metadata_json = db.Column(db.JSON, nullable=False, default=dict)
    credential_ref = db.Column(db.String(128), nullable=True)
    provider_account_ref = db.Column(db.String(255), nullable=True)
    provider_project_ref = db.Column(db.String(255), nullable=True)
    last_verified_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id", "user_id", "provider_id", "mode",
            name="uq_provider_connection_scope",
        ),
    )
