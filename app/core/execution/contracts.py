from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ExecutionRequest:
    action: str
    organization_id: int | None = None
    actor_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = True


@dataclass(slots=True)
class ExecutionResult:
    ok: bool
    action: str
    status: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
