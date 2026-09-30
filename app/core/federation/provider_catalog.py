from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.core.ai_federation import ai_federation
from app.core.model_intelligence import model_intelligence
from app.core.provider_factory import build_provider_adapters


@dataclass(frozen=True)
class ProviderCatalogEntry:
    provider_id: str
    display_name: str
    layer: str
    execution_ready: bool
    adapter_ready: bool
    configured: bool
    capabilities: tuple[str, ...]
    models: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "display_name": self.display_name,
            "layer": self.layer,
            "execution_ready": self.execution_ready,
            "adapter_ready": self.adapter_ready,
            "configured": self.configured,
            "capabilities": list(self.capabilities),
            "models": list(self.models),
        }


class ProviderCatalog:
    VERSION = "1.0"

    def all(self) -> tuple[ProviderCatalogEntry, ...]:
        adapters = build_provider_adapters()
        entries = []
        for profile in ai_federation.all():
            models = tuple(item.model_id for item in model_intelligence.for_provider(profile.provider_id))
            layer = "specialist" if profile.provider_id in {"manus", "meta"} else "intelligence"
            entries.append(ProviderCatalogEntry(
                profile.provider_id,
                profile.display_name,
                layer,
                profile.execution_ready,
                profile.provider_id in adapters,
                profile.is_configured(),
                tuple(sorted(profile.capabilities)),
                models,
            ))
        return tuple(entries)

    def get(self, provider_id: str) -> ProviderCatalogEntry | None:
        return next((item for item in self.all() if item.provider_id == provider_id), None)

    def snapshot(self, provider_ids: Iterable[str] | None = None) -> list[dict[str, object]]:
        allowed = set(provider_ids) if provider_ids is not None else None
        return [item.as_dict() for item in self.all() if allowed is None or item.provider_id in allowed]


provider_catalog = ProviderCatalog()
