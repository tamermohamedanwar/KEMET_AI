from app.services.payment_provider import PaymentProviderRegistry, PaymentRequest
from app.services.payment_provider_adapters import (
    PAYMENT_PROVIDER_NAMES,
    register_default_providers,
)


def test_registry_registers_supported_provider_names():
    registry = PaymentProviderRegistry()
    register_default_providers(registry)
    assert registry.names() == sorted(PAYMENT_PROVIDER_NAMES)


def test_unconfigured_provider_fails_closed_without_payment_execution():
    registry = PaymentProviderRegistry()
    register_default_providers(registry)
    provider = registry.get("paymob")
    request = PaymentRequest(1, "starter", "9", "USD")
    result = provider.create_checkout(request)
    assert result.status in {"not_configured", "requires_legacy_service"}
    assert result.checkout_url is None
    if result.status == "not_configured":
        assert result.raw["reason"] == "paymob_configuration_missing"


def test_paymob_adapter_does_not_execute_when_configuration_is_missing(monkeypatch):
    monkeypatch.delenv("PAYMOB_API_KEY", raising=False)
    registry = PaymentProviderRegistry()
    register_default_providers(registry)
    result = registry.get("paymob").create_checkout(
        PaymentRequest(1, "starter", "49", "USD")
    )
    assert result.status == "not_configured"
    assert result.provider == "paymob"


def test_unknown_provider_is_rejected():
    registry = PaymentProviderRegistry()
    try:
        registry.get("unknown")
    except ValueError as exc:
        assert "Unsupported payment provider" in str(exc)
    else:
        raise AssertionError("Unknown provider must be rejected")
