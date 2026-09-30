from app.core.federation.provider_catalog import provider_catalog


def test_catalog_exposes_global_provider_layers():
    snapshot = {item["provider_id"]: item for item in provider_catalog.snapshot()}
    for provider_id in (
        "openai", "anthropic", "google", "xai", "meta", "manus",
        "groq", "mistral", "deepseek", "cohere", "perplexity", "qwen",
        "microsoft", "aws", "ibm", "nvidia", "cerebras", "together", "fireworks", "moonshot",
    ):
        assert provider_id in snapshot


def test_catalog_distinguishes_adapter_readiness_from_execution_readiness():
    snapshot = {item["provider_id"]: item for item in provider_catalog.snapshot()}
    assert snapshot["groq"]["adapter_ready"] is True
    assert snapshot["meta"]["execution_ready"] is False
    assert snapshot["meta"]["adapter_ready"] is False


def test_catalog_never_reports_credentials():
    snapshot = provider_catalog.snapshot()
    serialized = repr(snapshot).lower()
    assert "api_key" not in serialized
    assert "authorization" not in serialized
    assert "secret" not in serialized


def test_catalog_marks_direct_adapters_as_execution_ready():
    snapshot = {item["provider_id"]: item for item in provider_catalog.snapshot()}
    for provider_id in ("groq", "mistral", "deepseek", "cohere", "perplexity", "qwen"):
        assert snapshot[provider_id]["adapter_ready"] is True
        assert snapshot[provider_id]["execution_ready"] is True
