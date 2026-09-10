"""Provider-neutral payment contracts for Kemet.

Providers implement preparation and verification behind this boundary.
No card data is stored here and no provider is executed automatically.
"""

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class PaymentRequest:
    organization_id: int
    plan: str
    amount: Any
    currency: str
    return_url: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class PaymentResult:
    status: str
    provider: str
    checkout_url: str | None = None
    provider_payment_id: str | None = None
    provider_order_id: str | None = None
    client_secret: str | None = None
    raw: dict[str, Any] | None = None


class PaymentProvider(Protocol):
    name: str

    def create_checkout(self, request: PaymentRequest) -> PaymentResult:
        ...

    def verify_payment(self, provider_payment_id: str) -> dict[str, Any]:
        ...


class PaymentProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, PaymentProvider] = {}

    def register(self, provider: PaymentProvider) -> None:
        name = str(provider.name).strip().lower()
        if not name:
            raise ValueError("Payment provider name is required")
        self._providers[name] = provider

    def get(self, name: str) -> PaymentProvider:
        key = str(name or "").strip().lower()
        provider = self._providers.get(key)
        if provider is None:
            raise ValueError(f"Unsupported payment provider: {key}")
        return provider

    def names(self) -> list[str]:
        return sorted(self._providers)


payment_provider_registry = PaymentProviderRegistry()

from app.services.payment_provider_adapters import register_default_providers

register_default_providers(payment_provider_registry)
