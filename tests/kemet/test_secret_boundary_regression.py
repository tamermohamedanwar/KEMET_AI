from app.core.secret_boundary import redact, secret_reference


def test_secret_reference_is_deterministic_without_exposing_secret():
    first = secret_reference("openai", "api_key")
    second = secret_reference("openai", "api_key")
    assert first == second
    assert first.startswith("secretref_")
    assert len(first) == 42
    assert "api_key" not in first


def test_secret_boundary_redacts_hyphenated_sensitive_keys():
    value = redact({
        "x-api-key": "secret-one",
        "access-token": "secret-two",
        "refresh-token": "secret-three",
        "client-secret": "secret-four",
        "set-cookie": "session=secret-five",
    })
    assert all(item == "[REDACTED]" for item in value.values())


def test_secret_reference_changes_with_provider_or_name():
    assert secret_reference("openai", "api_key") != secret_reference("anthropic", "api_key")
    assert secret_reference("openai", "api_key") != secret_reference("openai", "admin_key")
