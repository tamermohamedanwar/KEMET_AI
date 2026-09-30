import base64

from app import create_app, db
from app.services.social_connection_service import social_connection_service
from app.core.social_credential_store import social_credential_store
from app.core.social_oauth_lifecycle import social_oauth_lifecycle


def test_facebook_and_instagram_have_independent_publishing_specs():
    assert social_connection_service.SPECS["facebook"].client_key_env == "FACEBOOK_CLIENT_ID"
    assert social_connection_service.SPECS["instagram"].client_key_env == "INSTAGRAM_CLIENT_ID"
    assert social_connection_service.SPECS["facebook"].redirect_env != social_connection_service.SPECS["instagram"].redirect_env


def test_youtube_has_dedicated_publishing_oauth_spec():
    spec = social_connection_service.SPECS["youtube"]
    assert spec.provider == "google"
    assert spec.client_key_env == "GOOGLE_CLIENT_ID"
    assert spec.redirect_env == "GOOGLE_REDIRECT_URI"
    assert spec.token_url == "https://oauth2.googleapis.com/token"


def test_youtube_authorization_requires_publishing_configuration(monkeypatch):
    for key in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI", "YOUTUBE_PUBLISH_SCOPES"):
        monkeypatch.delenv(key, raising=False)
    result = social_connection_service.authorize(1, 1, "youtube")
    assert result["status"] == "setup_required"
    assert "GOOGLE_CLIENT_ID" in result["missing_configuration"]
    assert result["credentials_exposed"] is False


def test_social_authorization_persists_state_without_exposing_secret(monkeypatch):
    monkeypatch.setenv("FACEBOOK_CLIENT_ID", "fb-client")
    monkeypatch.setenv("FACEBOOK_CLIENT_SECRET", "fb-secret")
    monkeypatch.setenv("FACEBOOK_REDIRECT_URI", "https://example.test/facebook/callback")
    monkeypatch.setenv("META_PUBLISH_SCOPES", "pages_manage_posts,pages_read_engagement")
    app = create_app()
    with app.app_context():
        result = social_connection_service.authorize(1, 1, "facebook")
        assert result["status"] == "authorization_ready"
        assert result["credentials_exposed"] is False
        assert "fb-secret" not in result["authorization_url"]
        assert result["authorization_url"].startswith("https://www.facebook.com/")


def test_oauth_state_is_single_use_and_tenant_bound():
    app = create_app()
    with app.app_context():
        state = social_oauth_lifecycle.create_state(1, 1, "facebook")
        row = social_oauth_lifecycle.consume_state(state, 1, 1, "facebook")
        assert row.consumed_at is not None
        try:
            social_oauth_lifecycle.consume_state(state, 1, 1, "facebook")
            assert False
        except ValueError as exc:
            assert str(exc) == "oauth_state_replayed"


def test_encrypted_credential_store_round_trip(monkeypatch):
    monkeypatch.setenv("KEMET_OAUTH_ENCRYPTION_KEY", base64.urlsafe_b64encode(b"x" * 32).decode())
    app = create_app()
    with app.app_context():
        ref = social_credential_store.put(1, 1, "facebook", {"access_token": "secret-token", "refresh_token": "refresh-secret"})
        assert ref.startswith("oauthref_")
        assert social_credential_store.get(1, 1, "facebook")["access_token"] == "secret-token"
        row = social_credential_store.public_ref(1, 1, "facebook")
        assert row == ref
        assert "secret-token" not in row
