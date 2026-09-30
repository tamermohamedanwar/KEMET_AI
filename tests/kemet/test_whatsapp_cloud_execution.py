import pytest
from wsgi import application

from app.automation.action_registry import registry
from app.services.whatsapp_cloud_api_service import whatsapp_cloud_api_service


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self.ok = status_code < 400
        self.content = b"1"
        self._body = body or {"messages": [{"id": "wamid.test"}]}

    def json(self):
        return self._body


def test_direct_whatsapp_execution_requires_canonical_authorization(monkeypatch):
    called = []
    monkeypatch.setattr("app.services.whatsapp_cloud_api_service.governed_request", lambda *a, **k: called.append(1))
    result = whatsapp_cloud_api_service.execute_send_text(
        organization_id=7,
        recipient="201000000000",
        content="hello",
        external_message_id="in-1",
        phone_number_id="123456",
    )
    assert result["error"] == "canonical_execution_required"
    assert called == []


def test_canonical_whatsapp_send_uses_tenant_secret_and_no_leak(monkeypatch):
    monkeypatch.setenv("KEMET_META_ORG_7_ACCESS_TOKEN", "tenant-secret")
    calls = []

    def fake_post(method, url, **kwargs):
        calls.append((url, kwargs))
        return FakeResponse()

    monkeypatch.setattr("app.services.whatsapp_cloud_api_service.governed_request", fake_post)
    result = whatsapp_cloud_api_service.execute_send_text(
        organization_id=7,
        recipient="201000000000",
        content="hello",
        external_message_id="in-2",
        phone_number_id="123456",
        approved_execution=True,
        execution_authorization={"execution_key": "approval:1"},
    )
    assert result["success"] is True
    assert result["provider_message_id"] == "wamid.test"
    assert calls[0][0].startswith("https://graph.facebook.com/")
    assert calls[0][1]["headers"]["Authorization"] == "Bearer tenant-secret"
    assert "tenant-secret" not in str(result)


def test_wrong_tenant_secret_is_not_reused(monkeypatch):
    monkeypatch.setenv("KEMET_META_ORG_8_ACCESS_TOKEN", "other-tenant-secret")
    with application.app_context():
        result = whatsapp_cloud_api_service.execute_send_text(
        organization_id=7,
        recipient="201000000000",
        content="hello",
        external_message_id="in-3",
        phone_number_id="123456",
        approved_execution=True,
        execution_authorization={"execution_key": "approval:2"},
    )
    assert result["error"] == "secret_not_configured"


def test_provider_error_is_normalized_and_redacted(monkeypatch):
    monkeypatch.setenv("KEMET_META_ORG_7_ACCESS_TOKEN", "tenant-secret")
    monkeypatch.setattr(
        "app.services.whatsapp_cloud_api_service.governed_request",
        lambda *a, **k: FakeResponse(400, {"error": {"message": "bad request", "access_token": "leak"}}),
    )
    result = whatsapp_cloud_api_service.execute_send_text(
        organization_id=7,
        recipient="201000000000",
        content="hello",
        external_message_id="in-4",
        phone_number_id="123456",
        approved_execution=True,
        execution_authorization={"execution_key": "approval:3"},
    )
    assert result["error"] == "provider_rejected_request"
    assert "leak" not in str(result)
    assert "tenant-secret" not in str(result)


def test_action_registry_cannot_bypass_canonical_execution():
    result = registry.execute(
        "whatsapp_send_text",
        {"organization_id": 7, "recipient": "201000000000", "content": "hello"},
    )
    assert result["error"] == "canonical_execution_required"
