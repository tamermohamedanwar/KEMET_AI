from app.services.content_revenue_bridge_service import content_revenue_bridge_service


def _measurement(monkeypatch, metrics=None):
    monkeypatch.setattr(
        "app.services.content_revenue_bridge_service.publication_measurement_evidence_service.verify",
        lambda **kwargs: {
            "success": True,
            "verified": True,
            "provider": "meta_graph",
            "publication_evidence_id": "ev-pub",
            "metrics": metrics or {"post_impressions": 10000, "post_reach": 2500},
            "metric_provenance": {
                "post_impressions": "OBSERVED",
                "post_reach": "OBSERVED",
            },
            "metric_evidence_digest": "digest-1",
            "synthetic": False,
        },
    )


def test_bridge_requires_verified_publication_measurement(monkeypatch):
    _measurement(monkeypatch)
    result = content_revenue_bridge_service.measure_and_attribute(
        organization_id=7,
        user_id=11,
        channel="facebook",
        content_id="episode-7",
        publication_id="pub-7",
        execution_key="exec-7",
        payment_evidence=[
            {
                "stage": "payment.completed",
                "content_id": "episode-7",
                "provider_transaction_id": "tx-77",
                "receipt": {"amount": 500, "currency": "EGP", "provider_transaction_id": "tx-77"},
            }
        ],
    )
    assert result["provider_measurement"]["verified"] is True
    assert result["provider_measurement"]["publication_evidence_id"] == "ev-pub"
    assert result["commercial"]["revenue"]["amount"] == 500.0
    assert result["commercial"]["revenue"]["evidence_backed"] is True


def test_bridge_never_accepts_provider_metrics_as_revenue(monkeypatch):
    _measurement(monkeypatch, {
        "post_impressions": 1000,
        "post_reach": 500,
        "revenue": 999999,
    })
    result = content_revenue_bridge_service.measure_and_attribute(
        organization_id=7, user_id=11, channel="facebook",
        content_id="episode-8", publication_id="pub-8",
        execution_key="exec-8", payment_evidence=[],
    )
    assert result["commercial"]["revenue"]["amount"] == 0.0
    assert result["commercial"]["revenue"]["evidence_backed"] is False


def test_bridge_blocks_unverified_publication_measurement(monkeypatch):
    monkeypatch.setattr(
        "app.services.content_revenue_bridge_service.publication_measurement_evidence_service.verify",
        lambda **kwargs: {"success": False, "verified": False, "error": "publication_evidence_missing"},
    )
    result = content_revenue_bridge_service.measure_and_attribute(
        organization_id=7, user_id=11, channel="instagram",
        content_id="episode-9", publication_id="pub-9",
        execution_key="exec-9", payment_evidence=[],
    )
    assert result["status"] == "blocked"
    assert result["error"] == "publication_evidence_missing"
    assert result["governance"]["external_execution"] is False


def test_bridge_rejects_unsupported_authoritative_channel():
    import pytest
    with pytest.raises(ValueError, match="authoritative_channel_not_supported"):
        content_revenue_bridge_service.measure_and_attribute(
            organization_id=7, user_id=11, channel="youtube",
            content_id="episode-10", publication_id="pub-10",
            execution_key="exec-10",
        )
