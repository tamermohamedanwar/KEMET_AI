from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy.exc import IntegrityError

from app import db
from app.models.execution_authorization_consumption import ExecutionAuthorizationConsumption


class ExecutionAuthorizationStore:
    """Durable one-time authorization consumption with DB-enforced uniqueness."""

    VERSION = "1.0"

    @staticmethod
    def token_hash(token: str) -> str:
        return hashlib.sha256(str(token).encode("utf-8")).hexdigest()

    def consume(self, authorization: dict[str, Any], *, plan: dict[str, Any] | None = None, action: str | None = None) -> bool:
        token = str(authorization.get("token") or authorization.get("execution_token") or "")
        if not token:
            return False
        token_digest = self.token_hash(token)
        effective_plan = plan or authorization.get("_execution_plan") or {}
        effective_action = action or authorization.get("_execution_action") or authorization.get("action")
        row = ExecutionAuthorizationConsumption(
            token_hash=token_digest,
            organization_id=_int_or_none(effective_plan.get("organization_id")),
            plan_hash=str(authorization.get("plan_hash") or "") or None,
            action=str(effective_action or "") or None,
            approver_id=_int_or_none(authorization.get("approver_id")),
            execution_key=str(authorization.get("execution_key") or (plan or {}).get("execution_key") or "") or None,
            expires_at=_int_or_zero(authorization.get("expires_at")),
            consumed_at=datetime.utcnow(),
            created_at=datetime.utcnow(),
        )
        db.session.add(row)
        try:
            db.session.commit()
            return True
        except IntegrityError:
            db.session.rollback()
            return False


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None and str(value) != "" else None
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


execution_authorization_store = ExecutionAuthorizationStore()
