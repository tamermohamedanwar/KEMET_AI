from __future__ import annotations

from .context_models import ContextEnvelope, ContextSnapshot
from .conversation_registry import ConversationRegistry


class FederationContextGateway:
    VERSION = "1.0"

    def __init__(self, registry: ConversationRegistry | None = None):
        self.registry = registry or ConversationRegistry()

    def ingest(self, envelope: ContextEnvelope) -> dict:
        row = self.registry.upsert(envelope)
        return {
            "conversation_id": row.id,
            "provider_id": row.provider_id,
            "project_id": row.project_id,
            "task_id": row.task_id,
            "context_hash": row.context_hash,
            "status": "linked",
        }

    def snapshot(self, organization_id: int, user_id: int, project_id: str = "kemet-ai", task_id: str | None = None, termux: dict | None = None) -> ContextSnapshot:
        rows = self.registry.for_scope(organization_id, user_id, project_id, task_id)
        conversations = []
        for row in rows:
            conversations.append({
                "provider_id": row.provider_id,
                "external_conversation_id": row.external_conversation_id,
                "task_id": row.task_id,
                "role": row.role,
                "summary": row.summary,
                "decisions": row.decisions_json or [],
                "artifacts": row.artifacts_json or [],
                "context_hash": row.context_hash,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            })
        return ContextSnapshot(
            organization_id=organization_id,
            user_id=user_id,
            project_id=project_id,
            task_id=task_id,
            conversations=tuple(conversations),
            termux=_safe_termux(termux or {}),
        )


def _safe_termux(value: dict) -> dict:
    allowed = {"workspace", "branch", "last_test", "bridge_health", "agent_health", "milestone"}
    return {k: value[k] for k in allowed if k in value}
