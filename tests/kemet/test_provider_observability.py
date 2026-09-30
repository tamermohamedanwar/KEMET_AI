from app.core.ai_federation import AIFederationRegistry, ProviderProfile
from app.core.provider_health import ProviderHealthRegistry
from app.core.provider_observability import ProviderObservability


def test_health_snapshot_records_latency_and_resets_on_success():
    health = ProviderHealthRegistry(failure_threshold=2, cooldown_seconds=60)
    health.record_failure("openai", "timeout", latency_ms=12.5)
    assert health.snapshot()[0]["last_latency_ms"] == 12.5
    health.record_success("openai", latency_ms=8.25)
    state = health.snapshot()[0]
    assert state["healthy"] is True
    assert state["failures"] == 0
    assert state["last_error_type"] is None
    assert state["last_latency_ms"] == 8.25


def test_observability_snapshot_contains_catalog_without_secrets(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-value")
    registry = AIFederationRegistry([
        ProviderProfile("openai", "OpenAI", frozenset({"reasoning"}), 100, "OPENAI_API_KEY", primary=True),
    ])
    snapshot = ProviderObservability.__new__(ProviderObservability)
    monkeypatch.setattr("app.core.provider_observability.ai_federation", registry)
    monkeypatch.setattr("app.core.provider_observability.provider_health", ProviderHealthRegistry())
    data = snapshot.snapshot()
    assert data["providers"][0]["configured"] is True
    assert "secret-value" not in str(data)
    assert "OPENAI_API_KEY" not in str(data["providers"][0]["health"])
