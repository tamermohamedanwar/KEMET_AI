import pytest

from app.core.federation_policy import FederationPolicy
from app.core.model_intelligence import ModelIntelligenceRegistry
from app.core.provider_health import ProviderHealthRegistry
from app.core.provider_router import ProviderRouter
from app.core.ai_federation import AIFederationRegistry, ProviderProfile


def router():
    registry = AIFederationRegistry([
        ProviderProfile("openai", "OpenAI", frozenset({"reasoning", "coding"}), 100, "TEST_OPENAI", primary=True),
        ProviderProfile("google", "Google", frozenset({"reasoning", "coding", "research"}), 80, "TEST_GOOGLE"),
    ])
    models = ModelIntelligenceRegistry()
    return ProviderRouter(registry, ProviderHealthRegistry(), models)


def test_selects_model_by_capability_and_provider(monkeypatch):
    monkeypatch.setenv("TEST_OPENAI", "configured")
    decision = router().decide({"reasoning"}, require_configured=True)
    assert decision.provider_id == "openai"
    assert decision.model_id == "gpt-5.6"


def test_policy_allowed_model_is_enforced(monkeypatch):
    monkeypatch.setenv("TEST_OPENAI", "configured")
    policy = FederationPolicy(1, allowed_providers=frozenset({"openai"}), allowed_models=frozenset({"gpt-5.6"}))
    decision = router().decide({"reasoning"}, require_configured=True, policy=policy)
    assert decision.model_id == "gpt-5.6"


def test_disallowed_explicit_model_fails_closed(monkeypatch):
    monkeypatch.setenv("TEST_OPENAI", "configured")
    policy = FederationPolicy(1, allowed_providers=frozenset({"openai"}), allowed_models=frozenset({"gpt-5.6"}))
    with pytest.raises(LookupError):
        router().decide({"reasoning"}, require_configured=True, policy=policy, model="not-allowed")


def test_model_snapshot_has_no_credentials():
    snapshot = ModelIntelligenceRegistry().snapshot()
    assert snapshot
    assert all("api_key" not in item for item in snapshot)
