from __future__ import annotations

import os
from typing import Any

from app.core.federation.specialist_contracts import SpecialistAdapter, SpecialistRequest, SpecialistResponse


class MetaLlamaAdapter(SpecialistAdapter):
    provider_id = "meta"
    execution_kind = "model"
    capabilities = frozenset({"coding", "reasoning", "agentic", "tool_calling"})

    def configured(self) -> bool:
        return bool(os.getenv("META_API_KEY"))

    def build_request(self, request: SpecialistRequest) -> dict[str, Any]:
        super().build_request(request)
        if not self.configured():
            raise RuntimeError("META_API_KEY is not configured")
        return {"prompt": request.prompt, "model": request.model, "organization_id": request.organization_id}

    def health_check(self) -> SpecialistResponse:
        return SpecialistResponse(
            provider_id=self.provider_id,
            task_id="health",
            status="configured" if self.configured() else "requires_user_action",
            metadata={"live_verification": False},
        )
