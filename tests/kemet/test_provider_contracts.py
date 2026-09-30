from app.core.ai_federation import AIFederationRegistry
from app.core.provider_contracts import ProviderRequest
from app.core.provider_router import ProviderRouter


def test_router_selects_explicit_capable_provider_without_credentials_for_catalog_mode():
    decision = ProviderRouter(AIFederationRegistry()).decide({"coding"}, preferred="xai")
    assert decision.provider_id == "xai"
    assert decision.reason == "explicit_preference"


def test_provider_request_is_provider_neutral():
    request = ProviderRequest(prompt="hello", required_capabilities=frozenset({"reasoning"}))
    assert request.prompt == "hello"
    assert request.required_capabilities == {"reasoning"}
