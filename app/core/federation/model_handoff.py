from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import time


@dataclass(frozen=True)
class ModelHandoff:
    organization_id: int
    user_id: int
    source_provider: str
    target_provider: str
    task_id: str
    context_hash: str
    context: dict
    requested_role: str
    issued_at: int
    expires_at: int
    handoff_hash: str

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _digest(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def create_handoff(*, organization_id: int, user_id: int, source_provider: str, target_provider: str, task_id: str, context: dict, requested_role: str, ttl_seconds: int = 300) -> ModelHandoff:
    now = int(time.time())
    safe_context = {k: v for k, v in context.items() if k not in {"token", "secret", "password", "api_key", "authorization", "cookie"}}
    context_hash = _digest(safe_context)
    payload = {
        "organization_id": organization_id, "user_id": user_id,
        "source_provider": source_provider, "target_provider": target_provider,
        "task_id": task_id, "context_hash": context_hash,
        "context": safe_context, "requested_role": requested_role,
        "issued_at": now, "expires_at": now + max(30, min(ttl_seconds, 900)),
    }
    return ModelHandoff(**payload, handoff_hash=_digest(payload))


def verify_handoff(handoff: ModelHandoff, *, organization_id: int, user_id: int, target_provider: str | None = None) -> bool:
    if handoff.organization_id != organization_id or handoff.user_id != user_id:
        return False
    if target_provider and handoff.target_provider != target_provider:
        return False
    if handoff.expires_at < int(time.time()):
        return False
    payload = handoff.as_dict().copy()
    payload.pop("handoff_hash", None)
    if _digest(payload) != handoff.handoff_hash:
        return False
    return _digest(handoff.context) == handoff.context_hash
