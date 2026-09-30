from app import db


class FederationConversation(db.Model):
    __tablename__ = "federation_conversations"
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    provider_id = db.Column(db.String(64), nullable=False, index=True)
    external_conversation_id = db.Column(db.String(255), nullable=False)
    project_id = db.Column(db.String(128), nullable=False, default="kemet-ai")
    task_id = db.Column(db.String(128), nullable=True, index=True)
    role = db.Column(db.String(64), nullable=False, default="participant")
    summary = db.Column(db.Text, nullable=False, default="")
    decisions_json = db.Column(db.JSON, nullable=False, default=list)
    artifacts_json = db.Column(db.JSON, nullable=False, default=list)
    source_metadata_json = db.Column(db.JSON, nullable=False, default=dict)
    context_hash = db.Column(db.String(64), nullable=False, index=True)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)
    __table_args__ = (
        db.UniqueConstraint("organization_id", "provider_id", "external_conversation_id", name="uq_fed_conv_org_provider_external"),
    )


class FederationSession(db.Model):
    __tablename__ = "federation_sessions"
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey("organizations.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    session_id = db.Column(db.String(128), nullable=False)
    project_id = db.Column(db.String(128), nullable=False, default="kemet-ai")
    task_id = db.Column(db.String(128), nullable=True, index=True)
    providers_json = db.Column(db.JSON, nullable=False, default=list)
    context_hash = db.Column(db.String(64), nullable=False)
    state_json = db.Column(db.JSON, nullable=False, default=dict)
    active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now(), nullable=False)
    __table_args__ = (
        db.UniqueConstraint("organization_id", "session_id", name="uq_fed_session_org_id"),
    )
