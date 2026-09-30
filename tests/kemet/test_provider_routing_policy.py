import pytest

from app.core.ai_federation import AIFederationRegistry, ProviderProfile
from app.core.provider_health import ProviderHealthRegistry
from app.core.provider_router import ProviderRouter


def test_router_fails_over_from_unhealthy_preference():
    health = ProviderHealthRegistry(failure_threshold=1, cooldown_seconds=60)
    health.record_failure("openai", "timeout")
    registry = AIFederationRegistry([
        ProviderProfile("openai", "OpenAI", frozenset({"reasoning"}), 100, "OPENAI_API_KEY"),
        ProviderProfile("anthropic", "Anthropic", frozenset({"reasoning"}), 90, "ANTHROPIC_API_KEY"),
    ])
    decision = ProviderRouter(registry, health).decide({"reasoning"}, preferred="openai")
    assert decision.provider_id == "anthropic"
    assert decision.reason == "capability_priority"


def test_health_recovers_after_success():
    health = ProviderHealthRegistry(failure_threshold=1, cooldown_seconds=60)
    health.record_failure("openai", "timeout")
    assert not health.is_healthy("openai")
    health.record_success("openai")
    assert health.is_healthy("openai")


def test_router_requires_configured_provider_when_requested(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    registry = AIFederationRegistry([
        ProviderProfile("openai", "OpenAI", frozenset({"reasoning"}), 100, "OPENAI_API_KEY"),
    ])
    with pytest.raises(LookupError):
        ProviderRouter(registry).decide({"reasoning"}, require_configured=True)


def test_federated_generate_falls_back_after_transient_provider_failure(monkeypatch):
    from app.core import provider_factory
    from app.core.provider_contracts import ProviderResponse, ProviderUnavailable

    class Failing:
        def generate(self, request):
            raise ProviderUnavailable("timeout")

    class Working:
        def generate(self, request):
            return ProviderResponse(content="fallback", provider_id="xai", model="test")

    registry = AIFederationRegistry([
        ProviderProfile("openai", "OpenAI", frozenset({"reasoning"}), 100, "OPENAI_API_KEY"),
        ProviderProfile("xai", "xAI", frozenset({"reasoning"}), 90, "XAI_API_KEY"),
    ])
    monkeypatch.setenv("OPENAI_API_KEY", "configured")
    monkeypatch.setenv("XAI_API_KEY", "configured")
    monkeypatch.setattr(provider_factory, "ai_federation", registry)
    monkeypatch.setattr(provider_factory, "provider_health", ProviderHealthRegistry(failure_threshold=1, cooldown_seconds=60))
    monkeypatch.setattr(provider_factory, "build_provider_adapters", lambda: {"openai": Failing(), "xai": Working()})
    result = provider_factory.federated_generate("hello", preferred="openai", required_capabilities={"reasoning"})
    assert result.content == "fallback"
    assert result.provider_id == "xai"
