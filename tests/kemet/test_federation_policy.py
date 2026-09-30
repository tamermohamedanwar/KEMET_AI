import os

import pytest

from app.core.ai_federation import AIFederationRegistry, ProviderProfile
from app.core.federation_policy import FederationPolicyRegistry
from app.core.provider_router import ProviderRouter
from app.core.provider_health import ProviderHealthRegistry


def test_tenant_policy_scopes_allowed_providers_and_capabilities():
    registry = FederationPolicyRegistry({
        "default": {"allowed_providers": ["openai"]},
        "organizations": {"7": {"allowed_providers": ["google"], "preferred_provider": "google",
                                  "required_capabilities": ["research"]}},
    })
    policy = registry.for_organization(7)
    assert policy.provider_allowed("google")
    assert not policy.provider_allowed("openai")
    assert "research" in policy.required_capabilities


def test_router_enforces_tenant_provider_policy():
    profiles = [ProviderProfile("openai", "OpenAI", frozenset({"reasoning"}), 100),
                ProviderProfile("google", "Google", frozenset({"reasoning", "research"}), 80)]
    router = ProviderRouter(AIFederationRegistry(profiles), ProviderHealthRegistry())
    policy = FederationPolicyRegistry({"organizations": {"9": {"allowed_providers": ["google"]}}}).for_organization(9)
    decision = router.decide({"reasoning"}, policy=policy)
    assert decision.provider_id == "google"


def test_router_fails_closed_when_policy_excludes_all_providers():
    profiles = [ProviderProfile("openai", "OpenAI", frozenset({"reasoning"}), 100)]
    router = ProviderRouter(AIFederationRegistry(profiles), ProviderHealthRegistry())
    policy = FederationPolicyRegistry({"organizations": {"9": {"allowed_providers": ["google"]}}}).for_organization(9)
    with pytest.raises(LookupError):
        router.decide({"reasoning"}, policy=policy)


def test_policy_snapshot_never_contains_secret_values(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "super-secret")
    registry = FederationPolicyRegistry({"default": {"allowed_providers": ["openai"]}})
    policy = registry.for_organization(1)
    assert policy.provider_allowed("openai")
    assert "super-secret" not in repr(policy)
