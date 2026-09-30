from app.services.content_commercial_loop_service import content_commercial_loop_service


def test_content_commercial_loop_binds_observed_distribution_to_verified_payment():
    result = content_commercial_loop_service.evaluate(
        organization_id=7,
        content_id="episode-7",
        channel="facebook",
        publication_id="pub-7",
        metrics={"views": 10000, "qualified_views": 2500, "retention_rate": 52},
        payment_evidence=[
            {
                "stage": "payment.completed",
                "receipt": {
                    "content_id": "episode-7",
                    "payment_id": 77,
                    "amount": 500,
                    "currency": "EGP",
                    "provider_transaction_id": "tx-77",
                },
            }
        ],
    )
    assert result["publication"]["metric_provenance"] == "OBSERVED"
    assert result["commercial"]["revenue"]["amount"] == 500.0
    assert result["commercial"]["revenue"]["evidence_backed"] is True
    assert result["commercial"]["attribution"]["causal_claim"] is False
    assert result["governance"]["execution_authority"] is False


def test_content_commercial_loop_does_not_infer_revenue_from_metrics():
    result = content_commercial_loop_service.evaluate(
        organization_id=7,
        content_id="episode-8",
        channel="instagram",
        publication_id="pub-8",
        metrics={"views": 10000, "qualified_views": 2500, "revenue": 999999},
        payment_evidence=[],
    )
    assert result["commercial"]["revenue"]["amount"] == 0.0
    assert result["commercial"]["revenue"]["evidence_backed"] is False
    assert result["commercial"]["economics"]["revenue_per_1000_qualified_views"] is None


def test_content_commercial_loop_requires_tenant():
    import pytest
    with pytest.raises(ValueError, match="organization_required"):
        content_commercial_loop_service.evaluate(
            organization_id=0,
            content_id="episode-9",
            channel="facebook",
            publication_id="pub-9",
            metrics={},
        )


def test_verified_loop_sources_measurement_and_payment_from_execution_evidence(monkeypatch):
    history = [
        {"stage": "payment.completed", "organization_id": 7, "execution_key": "exec-1", "receipt": {"content_id": "c1", "amount": 125, "provider_transaction_id": "tx-1"}},
    ]
    monkeypatch.setattr("app.services.content_commercial_loop_service.execution_evidence.history", lambda organization_id, execution_key: history)
    monkeypatch.setattr("app.services.content_commercial_loop_service.publication_measurement_evidence_service.verify", lambda **kwargs: {
        "success": True, "verified": True, "provider": "meta_graph", "metrics": {"views": 1000, "reach": 400},
        "publication_evidence_id": "pe-1", "metric_evidence_digest": "digest-1", "metric_provenance": {"source": "meta"},
    })
    monkeypatch.setattr("app.services.content_commercial_loop_service.revenue_identity_reconciliation_service.reconcile", lambda **kwargs: {
        "status": "reconciled", "identity": {"content_id": "c1", "publication_id": "p1", "execution_key": "exec-1"}
    })
    result = content_commercial_loop_service.evaluate_verified(
        organization_id=7, user_id=9, content_id="c1", channel="facebook", publication_id="p1", execution_key="exec-1"
    )
    assert result["commercial"]["revenue"]["amount"] == 125.0
    assert result["reconciliation"]["status"] == "reconciled"
    assert result["provider_measurement"]["metric_evidence_digest"] == "digest-1"
    assert result["execution_key"] == "exec-1"


def test_verified_loop_blocks_unverified_measurement(monkeypatch):
    monkeypatch.setattr("app.services.content_commercial_loop_service.execution_evidence.history", lambda **kwargs: [])
    monkeypatch.setattr("app.services.content_commercial_loop_service.publication_measurement_evidence_service.verify", lambda **kwargs: {
        "success": False, "verified": False, "error": "publication_evidence_required"
    })
    result = content_commercial_loop_service.evaluate_verified(
        organization_id=7, user_id=9, content_id="c2", channel="facebook", publication_id="p2", execution_key="exec-2"
    )
    assert result["success"] is False
    assert result["status"] == "blocked"
    assert result["error"] == "publication_evidence_required"
