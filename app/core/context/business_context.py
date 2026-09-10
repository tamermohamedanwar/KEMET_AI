from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BusinessContext:
    organization_id: int | None = None
    industry: str | None = None
    locale: str = "en"
    currency: str = "USD"
    facts: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "industry": self.industry,
            "locale": self.locale,
            "currency": self.currency,
            "facts": self.facts,
        }
