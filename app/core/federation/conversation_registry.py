from __future__ import annotations

from app import db
from app.models.federation import FederationConversation
from .context_models import ContextEnvelope


class ConversationRegistry:
    VERSION = "1.0"

    @staticmethod
    def upsert(envelope: ContextEnvelope) -> FederationConversation:
        envelope.validate()
        row = FederationConversation.query.filter_by(
            organization_id=envelope.organization_id,
            provider_id=envelope.provider_id,
            external_conversation_id=envelope.external_conversation_id,
        ).first()
        if row is None:
            row = FederationConversation(
                organization_id=envelope.organization_id,
                provider_id=envelope.provider_id,
                external_conversation_id=envelope.external_conversation_id,
            )
            db.session.add(row)
        row.user_id = envelope.user_id
        row.project_id = envelope.project_id
        row.task_id = envelope.task_id
        row.role = envelope.role
        row.summary = envelope.summary
        row.decisions_json = list(envelope.decisions)
        row.artifacts_json = list(envelope.artifacts)
        row.source_metadata_json = _safe_metadata(envelope.source_metadata)
        row.context_hash = envelope.fingerprint()
        row.active = True
        db.session.commit()
        return row

    @staticmethod
    def for_scope(organization_id: int, user_id: int, project_id: str, task_id: str | None = None):
        query = FederationConversation.query.filter_by(
            organization_id=organization_id,
            user_id=user_id,
            project_id=project_id,
            active=True,
        )
        if task_id:
            query = query.filter_by(task_id=task_id)
        return query.order_by(FederationConversation.updated_at.desc()).limit(50).all()


def _safe_metadata(metadata: dict) -> dict:
    blocked = ("token", "secret", "password", "api_key", "authorization", "cookie")
    return {k: v for k, v in metadata.items() if not any(x in k.lower() for x in blocked)}
