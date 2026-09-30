from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.provider_contracts import ProviderRequest, ProviderResponse


class ProviderAdapter(ABC):
    provider_id: str

    @abstractmethod
    def generate(self, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError
