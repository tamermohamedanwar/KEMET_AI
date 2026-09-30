from app.core.provider_resilience import ProviderResilienceRegistry


def test_provider_catalog_contains_multiple_fallback_classes():
    registry = ProviderResilienceRegistry()
    catalog = {item["provider_id"]: item for item in registry.catalog()}
    assert {"openai", "anthropic", "google", "xai", "groq", "openrouter", "huggingface", "cloudflare"}.issubset(catalog)
    assert catalog["openrouter"]["free_or_low_cost"] is True
    assert catalog["huggingface"]["free_or_low_cost"] is True


def test_rate_limit_and_billing_are_distinct_failure_classes():
    registry = ProviderResilienceRegistry()
    assert registry.classify_failure(Exception("quota exceeded")) == "quota"
    class RateLimited(Exception):
        status_code = 429
    assert registry.classify_failure(RateLimited("429")) == "rate_limit"
    class Billing(Exception):
        status_code = 402
    assert registry.classify_failure(Billing("402")) == "billing"


def test_penalty_temporarily_removes_provider_from_routing():
    registry = ProviderResilienceRegistry()
    registry.penalize("openai", "rate_limit", retry_after=60)
    assert registry.available("openai") is False
    assert registry.status()[0]["last_failure_class"] == "rate_limit"
