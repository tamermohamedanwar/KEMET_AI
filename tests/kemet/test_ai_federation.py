import pytest

from app.core.ai_federation import AIFederationRegistry, ProviderProfile


def test_defaults_make_openai_primary_and_provider_neutral():
    registry = AIFederationRegistry()
    assert registry.get("openai").primary is True
    expected = {
        "openai", "anthropic", "google", "xai", "meta", "manus", "openrouter",
        "groq", "mistral", "deepseek", "cohere", "perplexity", "qwen",
        "microsoft", "aws", "ibm", "nvidia", "cerebras", "together", "fireworks", "moonshot", "codecraft",
    }
    assert {p.provider_id for p in registry.all()} == expected


def test_selection_prefers_explicit_provider_when_capable():
    registry = AIFederationRegistry()
    selected = registry.select({"coding"}, preferred="anthropic")
    assert selected.provider_id == "anthropic"


def test_selection_fails_closed_when_capability_is_unavailable():
    registry = AIFederationRegistry(
        [ProviderProfile("limited", "Limited", frozenset({"research"}), 1, "LIMITED_KEY")]
    )
    with pytest.raises(LookupError):
        registry.select({"coding"})
