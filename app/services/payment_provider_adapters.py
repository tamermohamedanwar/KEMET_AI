"""Payment provider adapters behind the provider-neutral boundary."""

import os
from typing import Any

import requests

from app.services.payment_provider import PaymentRequest, PaymentResult


class ConfiguredProvider:
    """Fail-closed adapter for providers without an implementation."""

    def __init__(self, name: str) -> None:
        self.name = name

    def create_checkout(self, request: PaymentRequest) -> PaymentResult:
        return PaymentResult(
            status="not_configured",
            provider=self.name,
            raw={"reason": "provider_adapter_not_implemented"},
        )

    def verify_payment(self, provider_payment_id: str) -> dict[str, Any]:
        return {
            "status": "not_configured",
            "provider": self.name,
            "verified": False,
            "provider_payment_id": provider_payment_id,
        }


class PaymobProvider:
    """Provider-neutral Paymob adapter for checkout preparation."""

    name = "paymob"

    def create_checkout(self, request: PaymentRequest) -> PaymentResult:
        if not self.configured():
            return PaymentResult(
                status="not_configured",
                provider=self.name,
                raw={"reason": "paymob_configuration_missing"},
            )

        return PaymentResult(
            status="requires_legacy_service",
            provider=self.name,
            raw={"reason": "use_payment_service_until_migration"},
        )

    def verify_payment(self, provider_payment_id: str) -> dict[str, Any]:
        return {
            "status": "requires_legacy_service",
            "provider": self.name,
            "verified": False,
            "provider_payment_id": provider_payment_id,
        }

    @staticmethod
    def configured() -> bool:
        names = (
            "PAYMOB_API_KEY",
            "PAYMOB_SECRET_KEY",
            "PAYMOB_PUBLIC_KEY",
            "PAYMOB_INTEGRATION_ID",
        )
        return all(os.getenv(name, "").strip() for name in names)


PAYMENT_PROVIDER_NAMES = (
    "mock",
    "paymob",
    "fawry",
    "kashier",
    "stripe",
)


def register_default_providers(registry) -> None:
    registry.register(PaymobProvider())
    for name in PAYMENT_PROVIDER_NAMES:
        if name != "paymob":
            registry.register(ConfiguredProvider(name))
