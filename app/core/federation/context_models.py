from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ContextEnvelope:
    provider_id: str
    external_conversation_id: str
    organization_id: int
    user_id: int
    project_id: str = "kemet-ai"
    task_id: str | None = None
    role: str = "participant"
    summary: str = ""
    decisions: tuple[str, ...] = ()
    artifacts: tuple[dict[str, Any], ...] = ()
    source_metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def validate(self) -> None:
        if not self.provider_id or not self.external_conversation_id:
            raise ValueError("provider_id and external_conversation_id are required")
        if self.organization_id <= 0 or self.user_id <= 0:
            raise ValueError("positive organization_id and user_id are required")
        if len(self.summary) > 12000:
            raise ValueError("summary exceeds context limit")
        if len(self.decisions) > 100 or len(self.artifacts) > 100:
            raise ValueError("context item limit exceeded")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "provider_id": self.provider_id,
            "external_conversation_id": self.external_conversation_id,
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "role": self.role,
            "summary": self.summary,
            "decisions": list(self.decisions),
            "artifacts": list(self.artifacts),
            "source_metadata": _safe_metadata(self.source_metadata),
            "created_at": self.created_at,
        }

    def fingerprint(self) -> str:
        return fingerprint(self.as_dict())


@dataclass(frozen=True)
class ContextSnapshot:
    organization_id: int
    user_id: int
    project_id: str
    task_id: str | None
    conversations: tuple[dict[str, Any], ...]
    termux: dict[str, Any]
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "conversations": list(self.conversations),
            "termux": self.termux,
            "generated_at": self.generated_at,
        }

    def fingerprint(self) -> str:
        return fingerprint(self.as_dict())


def _safe_metadata(value: dict[str, Any]) -> dict[str, Any]:
    blocked = ("token", "secret", "password", "api_key", "authorization", "cookie")
    return {k: v for k, v in value.items() if not any(x in k.lower() for x in blocked)}
