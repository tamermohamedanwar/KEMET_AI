from app.core.provider_adapters import build_provider_adapters
from app.core.provider_contracts import ProviderConfigurationError, ProviderRequest


def test_provider_catalog_has_runtime_adapters():
    adapters = build_provider_adapters()
    assert {"openai", "anthropic", "google", "xai", "openrouter", "codecraft"}.issubset(adapters)


def test_openai_and_xai_use_responses_contract(monkeypatch):
    captured = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "resp_test", "model": "test-model", "status": "completed", "output_text": "ok", "usage": {"input_tokens": 2, "output_tokens": 3, "total_tokens": 5}}

    def fake_post(method, url, **kwargs):
        captured.append((url, kwargs))
        return Response()

    monkeypatch.setattr("app.core.provider_http_adapter.governed_request", fake_post)
    monkeypatch.setenv("OPENAI_API_KEY", "test-openai")
    monkeypatch.setenv("XAI_API_KEY", "test-xai")
    adapters = build_provider_adapters()
    request = ProviderRequest(prompt="hello")
    assert adapters["openai"].generate(request).content == "ok"
    assert adapters["xai"].generate(request).total_tokens == 5
    assert captured[0][0].endswith("/responses")
    assert captured[1][0].endswith("/responses")
    assert captured[0][1]["json"]["store"] is False


def test_codecraft_uses_openai_chat_completions_contract(monkeypatch):
    monkeypatch.setenv("CODECRAFT_API_KEY", "test-codecraft")
    captured = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "id": "chatcmpl_test",
                "model": "gpt-5.6-sol",
                "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7},
            }

    def fake_post(method, url, **kwargs):
        captured.append((url, kwargs))
        return Response()

    monkeypatch.setattr("app.core.provider_http_adapter.governed_request", fake_post)
    result = build_provider_adapters()["codecraft"].generate(
        ProviderRequest(prompt="hello", system="be concise")
    )
    assert result.content == "ok"
    assert result.total_tokens == 7
    assert result.provider_id == "codecraft"
    assert captured[0][0] == "https://codecraftapi.com/v1/chat/completions"
    assert captured[0][1]["headers"]["Authorization"] == "Bearer test-codecraft"
    assert captured[0][1]["json"]["model"] == "gpt-5.6-sol"
    assert captured[0][1]["json"]["messages"][0] == {"role": "system", "content": "be concise"}


def test_codecraft_requires_credentials(monkeypatch):
    monkeypatch.delenv("CODECRAFT_API_KEY", raising=False)
    try:
        build_provider_adapters()["codecraft"].generate(ProviderRequest(prompt="hello"))
    except ProviderConfigurationError as exc:
        assert "credentials" in str(exc)
    else:
        raise AssertionError("expected missing credentials to fail closed")


def test_anthropic_requires_credentials(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    try:
        build_provider_adapters()["anthropic"].generate(ProviderRequest(prompt="hello"))
    except ProviderConfigurationError as exc:
        assert "credentials" in str(exc)
    else:
        raise AssertionError("expected missing credentials to fail closed")


def test_google_uses_gemini_key_compatibility(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    captured = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "int_test", "model": "gemini-test", "output_text": "ok", "status": "completed"}

    def fake_post(method, url, **kwargs):
        captured.append((url, kwargs))
        return Response()

    monkeypatch.setattr("app.core.provider_http_adapter.governed_request", fake_post)
    result = build_provider_adapters()["google"].generate(ProviderRequest(prompt="hello"))
    assert result.content == "ok"
    assert captured[0][0].endswith("/v1beta/interactions")
    assert captured[0][1]["headers"]["x-goog-api-key"] == "test-gemini"


def test_google_uses_current_interactions_contract(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini")
    captured = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "int_test", "model": "gemini-3.8-flash", "status": "completed", "steps": [{"type": "model_output", "content": [{"type": "text", "text": "ok"}]}], "usage": {"total_input_tokens": 2, "total_output_tokens": 3, "total_tokens": 5}}

    def fake_post(method, url, **kwargs):
        captured.append((url, kwargs))
        return Response()

    monkeypatch.setattr("app.core.provider_http_adapter.governed_request", fake_post)
    result = build_provider_adapters()["google"].generate(ProviderRequest(prompt="hello", system="be concise"))
    assert result.content == "ok"
    assert captured[0][0].endswith("/v1beta/interactions")
    assert captured[0][1]["headers"]["x-goog-api-key"] == "test-gemini"
    assert captured[0][1]["json"]["store"] is False
    assert captured[0][1]["json"]["system_instruction"] == "be concise"
