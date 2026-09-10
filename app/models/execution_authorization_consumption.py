from datetime import datetime

from app import db


class ExecutionAuthorizationConsumption(db.Model):
    __tablename__ = "execution_authorization_consumption"

    id = db.Column(db.Integer, primary_key=True)
    token_hash = db.Column(db.String(128), nullable=False, unique=True, index=True)
    organization_id = db.Column(db.Integer, nullable=True, index=True)
    plan_hash = db.Column(db.String(128), nullable=True, index=True)
    action = db.Column(db.String(255), nullable=True, index=True)
    approver_id = db.Column(db.Integer, nullable=True, index=True)
    execution_key = db.Column(db.String(512), nullable=True, index=True)
    expires_at = db.Column(db.Integer, nullable=False, index=True)
    consumed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
