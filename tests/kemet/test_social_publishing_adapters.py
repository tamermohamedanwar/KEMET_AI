from app import create_app, db
from app.core.execution.governed_executor import governed_execution_service
from app.services.social_publishing_adapters import PublishRequest, social_publishing_adapter


def _verified_facebook_connection(ref: str):
    from app.models.provider_connection import ProviderConnectionRecord
    row = ProviderConnectionRecord.query.filter_by(
        organization_id=1, user_id=1, provider_id="social:facebook", mode="official_connector"
    ).first()
    if row is None:
        row = ProviderConnectionRecord(organization_id=1, user_id=1, provider_id="social:facebook", mode="official_connector")
    row.status = "verified"
    row.credential_ref = ref
    row.provider_account_ref = ref.replace("oauthref_", "page-")
    row.scopes_json = ["pages_manage_posts"]
    row.metadata_json = {"publishing_capable": True}
    db.session.add(row)
    db.session.commit()
    return row


def test_facebook_and_instagram_publish_are_approval_gated():
    assert governed_execution_service._policy("facebook_publish") == "approval_required"
    assert governed_execution_service._policy("instagram_publish") == "approval_required"


def test_publish_fails_closed_without_verified_connection():
    app = create_app()
    with app.app_context():
        request = PublishRequest(1, 1, "facebook", "https://example.test/a.jpg", "image", dry_run=True)
        result = social_publishing_adapter.publish(request, execution_key="exec-no-connection")
        assert result["status"] == "blocked"
        assert result["error"] == "publishing_connection_not_ready"
        assert result["executed"] is False


def test_publish_fails_closed_when_connection_lacks_publishing_capability():
    app = create_app()
    with app.app_context():
        from app.models.provider_connection import ProviderConnectionRecord
        row = ProviderConnectionRecord(
            organization_id=1, user_id=1, provider_id="social:facebook",
            mode="official_connector", status="verified", credential_ref="oauthref_no_publish",
            provider_account_ref="page-no-publish", scopes_json=["pages_read_engagement"], metadata_json={"publishing_capable": False},
        )
        db.session.add(row)
        db.session.commit()
        request = PublishRequest(1, 1, "facebook", "https://example.test/a.jpg", "image", dry_run=True)
        result = social_publishing_adapter.publish(request, execution_key="exec-no-publish")
        assert result["status"] == "blocked"
        assert result["error"] == "publishing_capability_not_verified"
        assert result["executed"] is False


def test_publish_dry_run_requires_verified_connection(monkeypatch):
    app = create_app()
    with app.app_context():
        _verified_facebook_connection("oauthref_test")
        monkeypatch.setattr(social_publishing_adapter, "_record", lambda *args, **kwargs: None)
        request = PublishRequest(1, 1, "facebook", "https://example.test/a.jpg", "image", dry_run=True)
        result = social_publishing_adapter.publish(request, execution_key="exec-dry")
        assert result["status"] == "simulated"
        assert result["executed"] is False
        assert result["receipt"]["provider"] == "facebook"


def test_social_actions_registered_in_canonical_registry():
    registry = governed_execution_service._registry()
    assert registry.exists("facebook_publish")
    assert registry.exists("instagram_publish")


def test_publish_idempotency_reuses_receipt_across_execution_keys(monkeypatch):
    app = create_app()
    with app.app_context():
        _verified_facebook_connection("oauthref_idem")
        request = PublishRequest(
            1, 1, "facebook", "https://example.test/a.jpg", "image",
            idempotency_key="idem-cross-exec", content_id="asset-1", content_version=1,
            content_digest="d" * 64, publication_contract_digest="p" * 64, production_job_id="job-idem", publication_approval=True,
        )
        from app.services.mendes.mendes_publication_contract_service import mendes_publication_contract_service
        monkeypatch.setattr(mendes_publication_contract_service, "validate", lambda **kwargs: {"ready": True, "publication_contract_digest": "p" * 64})
        monkeypatch.setattr("app.services.social_publishing_adapters.social_credential_store.get", lambda *args: {"page_id": "page-idem", "page_access_token": "redacted-test-token"})
        monkeypatch.setattr(social_publishing_adapter, "_facebook", lambda *args: {"provider": "facebook", "publication_id": "pub-idem", "idempotency_key": "idem-cross-exec"})
        first = social_publishing_adapter.publish(request, execution_key="exec-one", approved_execution=True, execution_authorization={"authorized": True})
        second = social_publishing_adapter.publish(request, execution_key="exec-two", approved_execution=True, execution_authorization={"authorized": True})
        assert first["status"] == "published"
        assert second["status"] == "reused"
        assert second["idempotent"] is True


def test_publish_timeout_is_ambiguous_and_reconcilable(monkeypatch):
    app = create_app()
    with app.app_context():
        _verified_facebook_connection("oauthref_timeout")
        from app.services.mendes.mendes_publication_contract_service import mendes_publication_contract_service
        monkeypatch.setattr(mendes_publication_contract_service, "validate", lambda **kwargs: {"ready": True, "publication_contract_digest": "p" * 64})
        monkeypatch.setattr(social_publishing_adapter, "_facebook", lambda *args: (_ for _ in ()).throw(__import__("requests").Timeout()))
        monkeypatch.setattr("app.services.social_publishing_adapters.social_credential_store.get", lambda *args: {"page_id": "page-timeout", "page_access_token": "redacted-test-token"})
        request = PublishRequest(
            1, 1, "facebook", "https://example.test/a.jpg", "image",
            idempotency_key="idem-timeout", content_id="asset-timeout", content_version=1,
            content_digest="e" * 64, publication_contract_digest="p" * 64, production_job_id="job-timeout", publication_approval=True,
        )
        result = social_publishing_adapter.publish(request, execution_key="exec-timeout", approved_execution=True, execution_authorization={"authorized": True})
        assert result["status"] == "ambiguous"
        assert result["reconciliation_required"] is True
        assert result["receipt"]["error_classification"] == "timeout"
