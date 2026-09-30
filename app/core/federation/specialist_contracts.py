from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class SpecialistRequest:
    organization_id: int
    task_id: str
    prompt: str
    capabilities: tuple[str, ...] = ()
    model: str | None = None
    context_fingerprint: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SpecialistResponse:
    provider_id: str
    task_id: str
    status: str
    external_task_id: str | None = None
    content: str | None = None
    request_id: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


class SpecialistContractError(ValueError):
    pass


class SpecialistAdapter:
    provider_id = ""
    capabilities: frozenset[str] = frozenset()
    execution_kind = "model"

    def supports(self, required: set[str] | tuple[str, ...]) -> bool:
        return set(required).issubset(self.capabilities)

    def build_request(self, request: SpecialistRequest) -> Mapping[str, Any]:
        if request.organization_id <= 0 or not request.task_id or not request.prompt:
            raise SpecialistContractError("Invalid specialist request")
        return {"prompt": request.prompt, "model": request.model}
