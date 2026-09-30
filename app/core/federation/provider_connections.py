from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.ai_federation import ai_federation


@dataclass(frozen=True)
class ProviderConnection:
    provider_id: str
    mode: str
    status: str
    capabilities: tuple[str, ...]
    scopes: tuple[str, ...] = ()
    organization_id: int | None = None
    user_id: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    last_verified: str | None = None

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["capabilities"] = list(self.capabilities)
        data["scopes"] = list(self.scopes)
        data["metadata"] = _safe_metadata(self.metadata)
        return data


class ProviderConnectionRegistry:
    VERSION = "1.0"

    _MODES = {"api", "official_connector", "user_handoff", "native_chat_sync"}

    def __init__(self, env=None):
        self._env = env

    def capabilities(self, provider_id: str, organization_id: int, user_id: int) -> ProviderConnection:
        profile = ai_federation.get(provider_id)
        if profile is None:
            return ProviderConnection(provider_id, "api", "unsupported", (), organization_id=organization_id, user_id=user_id)
        configured = profile.is_configured()
        mode = "api" if profile.api_key_env else "user_handoff"
        status = "configured" if configured else "requires_user_action"
        return ProviderConnection(
            provider_id=provider_id, mode=mode, status=status,
            capabilities=tuple(sorted(profile.capabilities)),
            scopes=("generate",) if configured else (),
            organization_id=organization_id, user_id=user_id,
            metadata={"api_key_env": profile.api_key_env, "native_chat_sync": False},
            last_verified=datetime.now(timezone.utc).isoformat() if configured else None,
        )

    def all(self, organization_id: int, user_id: int) -> list[ProviderConnection]:
        return [self.capabilities(p.provider_id, organization_id, user_id) for p in ai_federation.all()]

    def register_handoff(self, provider_id: str, organization_id: int, user_id: int, metadata: dict[str, Any] | None = None) -> ProviderConnection:
        if not ai_federation.get(provider_id):
            raise ValueError("unsupported_provider")
        return ProviderConnection(
            provider_id=provider_id, mode="user_handoff", status="available",
            capabilities=tuple(sorted(ai_federation.get(provider_id).capabilities)),
            scopes=("context_ingest",), organization_id=organization_id, user_id=user_id,
            metadata=_safe_metadata(metadata or {}), last_verified=datetime.now(timezone.utc).isoformat(),
        )


def _safe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    blocked = ("token", "secret", "password", "api_key", "authorization", "cookie", "credential")
    return {k: v for k, v in metadata.items() if not any(x in k.lower() for x in blocked)}
