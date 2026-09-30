import uuid

from wsgi import application
from app import db
from app.models.organization import Organization
from app.core.federation.connection_lifecycle import ConnectionLifecycleService
import app.core.federation.connection_lifecycle as lifecycle


def _org(prefix):
    uid = uuid.uuid4().hex
    row = Organization(name=f"{prefix} {uid}", slug=f"{prefix.lower()}-{uid}")
    db.session.add(row)
    db.session.commit()
    return row


def test_live_verification_is_read_only_and_marks_verified(monkeypatch):
    with application.app_context():
        db.create_all()
        org = _org("Live Verify")
        row = ConnectionLifecycleService.register(org.id, 501, "openai")
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        class Response:
            def raise_for_status(self):
                return None
            def json(self):
                return {"data": [{"id": "model-a"}]}
        monkeypatch.setattr(lifecycle, "governed_request", lambda *a, **k: Response())
        result = ConnectionLifecycleService.verify(row, live=True)
        assert result["verified"] is True
        assert result["network_call"] is True
        assert row.status == "verified"
        assert row.last_verified_at is not None


def test_live_verification_failure_fails_closed(monkeypatch):
    with application.app_context():
        db.create_all()
        org = _org("Verify Fail")
        row = ConnectionLifecycleService.register(org.id, 502, "xai")
        monkeypatch.setenv("XAI_API_KEY", "test-key")
        def fail(*args, **kwargs):
            raise lifecycle.requests.RequestException("boom")
        monkeypatch.setattr(lifecycle.requests, "get", fail)
        result = ConnectionLifecycleService.verify(row, live=True)
        assert result["verified"] is False
        assert result["network_call"] is True
        assert row.status == "error"


def test_credential_reference_rejects_secret_like_values():
    with application.app_context():
        db.create_all()
        org = _org("Safe Ref")
        try:
            ConnectionLifecycleService.register(org.id, 503, "google", credential_ref="api_key_123")
            assert False
        except ValueError as exc:
            assert str(exc) == "unsafe_credential_ref"


def test_codecraft_live_verification(monkeypatch):
    with application.app_context():
        db.create_all()
        org = _org("CodeCraft Verify")
        row = ConnectionLifecycleService.register(org.id, 505, "codecraft")
        monkeypatch.setenv("CODECRAFT_API_KEY", "test-key")
        class Response:
            def raise_for_status(self):
                return None
            def json(self):
                return {"data": [{"id": "gpt-5.6-sol"}]}
        monkeypatch.setattr(lifecycle, "governed_request", lambda *a, **k: Response())
        result = ConnectionLifecycleService.verify(row, live=True)
        assert result["verified"] is True
        assert result["verification_supported"] is True
        assert result["network_call"] is True
        assert row.status == "verified"


def test_openrouter_live_verification(monkeypatch):
    with application.app_context():
        db.create_all()
        org = _org("OpenRouter Verify")
        row = ConnectionLifecycleService.register(org.id, 504, "openrouter")
        monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
        class Response:
            def raise_for_status(self):
                return None
            def json(self):
                return {"data": [{"id": "openrouter/model"}]}
        monkeypatch.setattr(lifecycle.requests, "get", lambda *a, **k: Response())
        result = ConnectionLifecycleService.verify(row, live=True)
        assert result["verified"] is True
        assert row.status == "verified"
        assert result["network_call"] is True
