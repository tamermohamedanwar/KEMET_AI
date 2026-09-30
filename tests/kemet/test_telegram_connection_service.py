import os

from app.services.telegram_connection_service import TelegramConnectionService


def test_unconfigured_fails_closed(monkeypatch):
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    result = TelegramConnectionService().preflight(channel_ref="@kemet")
    assert result["connection"] == "NOT_CONFIGURED"
    assert result["publishing_authority"] == "UNVERIFIED"
    assert result["token_exposed"] is False
    assert result["side_effect"] is False
    assert result["execution_authority"] is False


def test_preflight_never_exposes_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "fake-token-for-test")
    service = TelegramConnectionService()
    monkeypatch.setattr(service, "_get", lambda token, method, params=None: {"id": 1, "username": "kemet_bot", "is_bot": True} if method == "getMe" else {"id": -1001, "type": "channel", "title": "Kemet"} if method == "getChat" else [{"user": {"id": 1}, "status": "administrator", "can_post_messages": True}])
    result = service.preflight(channel_ref="@kemet")
    assert result["connection"] == "VERIFIED"
    assert result["publishing_authority"] == "VERIFIED"
    assert result["token_exposed"] is False
    assert "token" not in result


def test_api_failure_fails_closed(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "fake-token-for-test")
    service = TelegramConnectionService()
    def fail(*args, **kwargs):
        raise RuntimeError("boom")
    monkeypatch.setattr(service, "_get", fail)
    result = service.preflight(channel_ref="@kemet")
    assert result["connection"] == "FAILED_CLOSED"
    assert result["publishing_authority"] == "UNVERIFIED"
    assert result["execution_authority"] is False
