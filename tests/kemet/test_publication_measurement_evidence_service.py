from app.services.publication_measurement_evidence_service import publication_measurement_evidence_service


def test_telegram_admin_measurement_requires_human_verification():
    from app.services.publication_measurement_evidence_service import publication_measurement_evidence_service
    result = publication_measurement_evidence_service.verify_telegram_admin_measurement(
        organization_id=1, user_id=1, execution_key="x", publication_id="p",
        metrics={"views": 10}, source_ref="telegram-admin-export", human_verified=False,
    )
    assert result["verified"] is False
    assert result["error"] == "telegram_admin_verification_required"


def test_measurement_requires_verified_publication_receipt(monkeypatch):
    monkeypatch.setattr(
        "app.services.publication_measurement_evidence_service.publication_evidence_service.verify",
        lambda **kwargs: {
            "verified": True,
            "records": [{
                "evidence_id": "pub-ev",
                "channel": "facebook",
                "provider": "facebook",
                "publication_id": "post-1",
            }],
        },
    )
    monkeypatch.setattr(
        "app.services.publication_measurement_evidence_service.social_measurement_service.measure",
        lambda request: {
            "success": True,
            "verified": True,
            "metrics": {"post_impressions": 100, "post_reach": 20},
            "metric_provenance": {"post_impressions": "OBSERVED", "post_reach": "OBSERVED"},
        },
    )
    result = publication_measurement_evidence_service.verify(
        organization_id=7, user_id=11, execution_key="exec-1",
        channel="facebook", publication_id="post-1",
    )
    assert result["status"] == "measurement_verified"
    assert result["publication_evidence_id"] == "pub-ev"
    assert result["synthetic"] is False
    assert result["revenue_verified"] is False


def test_measurement_rejects_publication_identity_mismatch(monkeypatch):
    monkeypatch.setattr(
        "app.services.publication_measurement_evidence_service.publication_evidence_service.verify",
        lambda **kwargs: {
            "verified": True,
            "records": [{
                "evidence_id": "pub-ev",
                "channel": "facebook",
                "provider": "facebook",
                "publication_id": "other-post",
            }],
        },
    )
    result = publication_measurement_evidence_service.verify(
        organization_id=7, user_id=11, execution_key="exec-2",
        channel="facebook", publication_id="post-2",
    )
    assert result["error"] == "publication_identity_mismatch"
    assert result["verified"] is False


def test_measurement_blocks_without_publication_evidence(monkeypatch):
    monkeypatch.setattr(
        "app.services.publication_measurement_evidence_service.publication_evidence_service.verify",
        lambda **kwargs: {"verified": False, "records": []},
    )
    result = publication_measurement_evidence_service.verify(
        organization_id=7, user_id=11, execution_key="exec-3",
        channel="instagram", publication_id="media-3",
    )
    assert result["error"] == "publication_evidence_missing"
    assert result["verified"] is False
