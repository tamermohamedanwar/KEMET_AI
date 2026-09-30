from __future__ import annotations

from app import db
from app.models.federation import FederationSession
from .context_models import fingerprint


class CollaborationSessionService:
    VERSION = "1.0"

    @staticmethod
    def upsert(organization_id: int, user_id: int, session_id: str, project_id: str, task_id: str | None, providers: list[str], state: dict) -> FederationSession:
        if organization_id <= 0 or user_id <= 0 or not session_id:
            raise ValueError("valid organization, user, and session are required")
        providers = sorted(set(providers))
        row = FederationSession.query.filter_by(organization_id=organization_id, session_id=session_id).first()
        if row is None:
            row = FederationSession(organization_id=organization_id, session_id=session_id)
            db.session.add(row)
        row.user_id = user_id
        row.project_id = project_id or "kemet-ai"
        row.task_id = task_id
        row.providers_json = providers
        row.state_json = _safe_state(state)
        row.context_hash = fingerprint({"providers": providers, "state": row.state_json, "task_id": task_id})
        row.active = True
        db.session.commit()
        return row

    @staticmethod
    def get(organization_id: int, user_id: int, session_id: str) -> FederationSession | None:
        return FederationSession.query.filter_by(
            organization_id=organization_id,
            user_id=user_id,
            session_id=session_id,
            active=True,
        ).first()


def _safe_state(state: dict) -> dict:
    blocked = ("token", "secret", "password", "api_key", "authorization", "cookie")
    return {k: v for k, v in state.items() if not any(x in k.lower() for x in blocked)}
