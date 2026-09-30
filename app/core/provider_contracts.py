from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class ProviderRequest:
    prompt: str
    model: str | None = None
    system: str | None = None
    context: tuple[Mapping[str, Any], ...] = ()
    required_capabilities: frozenset[str] = frozenset()
    metadata: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ProviderResponse:
    content: str
    provider_id: str
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    request_id: str | None = None
    finish_reason: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ProviderContractError(RuntimeError):
    pass


class ProviderUnavailable(ProviderContractError):
    def __init__(self, message: str, *, status_code: int | None = None, retry_after: float | None = None, failure_class: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after
        self.failure_class = failure_class


class ProviderConfigurationError(ProviderContractError):
    pass
