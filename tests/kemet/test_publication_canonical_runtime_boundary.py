from app.services.social_publishing_adapters import PublishRequest, social_publishing_adapter
from app.services.tiktok_publishing_adapter import TikTokPublishRequest, tiktok_publishing_adapter


def test_facebook_real_publish_requires_canonical_runtime_authorization(monkeypatch):
    request = PublishRequest(1, 1, "facebook", "https://example.test/a.jpg", "image", production_job_id="job-1", publication_approval=True)
    monkeypatch.setattr(social_publishing_adapter, "preflight", lambda request: {"ready": True})
    result = social_publishing_adapter.publish(request, execution_key="exec-1")
    assert result["status"] == "blocked"
    assert result["error"] == "canonical_runtime_authorization_required"
    assert result["executed"] is False


def test_tiktok_real_publish_requires_canonical_runtime_authorization(monkeypatch):
    request = TikTokPublishRequest(1, 1, "https://example.test/video.mp4", production_job_id="job-1", publication_approval=True)
    monkeypatch.setattr(tiktok_publishing_adapter, "preflight", lambda request: {"ready": True})
    result = tiktok_publishing_adapter.publish(request, execution_key="exec-1")
    assert result["status"] == "blocked"
    assert result["error"] == "canonical_runtime_authorization_required"
    assert result["executed"] is False


def test_publication_contract_digest_is_required_for_real_publish(monkeypatch):
    from app.services.mendes.mendes_publication_contract_service import mendes_publication_contract_service
    request = PublishRequest(1, 1, "facebook", "https://example.test/a.jpg", "image", production_job_id="job-1", publication_approval=True, publication_contract_digest="tampered")
    monkeypatch.setattr(social_publishing_adapter, "preflight", lambda request: {"ready": True})
    monkeypatch.setattr("app.services.social_publishing_adapters.execution_evidence.history", lambda **kwargs: [])
    monkeypatch.setattr(social_publishing_adapter, "_record", lambda *args, **kwargs: None)
    monkeypatch.setattr(mendes_publication_contract_service, "validate", lambda **kwargs: {"ready": True, "publication_contract_digest": "expected"})
    result = social_publishing_adapter.publish(request, execution_key="exec-1", approved_execution=True, execution_authorization={"ok": True})
    assert result["status"] == "blocked"
    assert result["error"] == "publication_contract_digest_mismatch"


def test_dry_run_remains_simulatable_without_execution_authority(monkeypatch):
    request = PublishRequest(1, 1, "facebook", "https://example.test/a.jpg", "image", dry_run=True)
    monkeypatch.setattr(social_publishing_adapter, "preflight", lambda request: {"ready": True})
    monkeypatch.setattr("app.services.social_publishing_adapters.execution_evidence.history", lambda **kwargs: [])
    monkeypatch.setattr(social_publishing_adapter, "_record", lambda *args, **kwargs: None)
    result = social_publishing_adapter.publish(request, execution_key="exec-1")
    assert result["status"] == "simulated"
    assert result["executed"] is False
