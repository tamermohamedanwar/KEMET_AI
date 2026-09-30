from app.services.revenue_portfolio_service import revenue_portfolio_service


def test_aggregates_only_reconciled_revenue_by_channel():
    result = revenue_portfolio_service.aggregate(
        organization_id=1,
        content_results=[
            {"organization_id": 1, "content_id": "c1", "publication": {"channel": "facebook", "publication_id": "p1"}, "execution_key": "e1", "reconciliation": {"status": "reconciled", "identity": {"content_id": "c1", "publication_id": "p1", "execution_key": "e1"}}, "provider_measurement": {"verified": True, "metric_evidence_digest": "m1"}, "commercial": {"revenue": {"amount": 100}, "economics": {"qualified_views": 5000}}},
            {"organization_id": 1, "content_id": "c2", "publication": {"channel": "instagram", "publication_id": "p2"}, "execution_key": "e2", "reconciliation": {"status": "reconciled", "identity": {"content_id": "c2", "publication_id": "p2", "execution_key": "e2"}}, "provider_measurement": {"verified": True, "metric_evidence_digest": "m2"}, "commercial": {"revenue": {"amount": 50}, "economics": {"qualified_views": 1000}}},
            {"organization_id": 1, "content_id": "c3", "publication": {"channel": "facebook", "publication_id": "p3"}, "execution_key": "e3", "reconciliation": {"status": "not_reconciled"}, "provider_measurement": {"verified": True}, "commercial": {"revenue": {"amount": 999}, "economics": {"qualified_views": 99999}}},
        ],
    )
    assert result["portfolio"]["verified_revenue"] == 150
    assert result["portfolio"]["reconciled_content_count"] == 2
    assert {row["channel"] for row in result["channels"]} == {"facebook", "instagram"}
    assert result["decision_support"]["automatic_action"] is False


def test_ignores_other_tenants_and_invalid_organization():
    result = revenue_portfolio_service.aggregate(organization_id=1, content_results=[{"organization_id": 2, "content_id": "x"}])
    assert result["portfolio"]["verified_revenue"] == 0
    try:
        revenue_portfolio_service.aggregate(organization_id=0)
    except ValueError as exc:
        assert str(exc) == "organization_required"
    else:
        raise AssertionError("expected organization_required")


def test_payment_evidence_overrides_claimed_revenue_amount_and_reconciliation_status():
    from unittest.mock import patch

    with patch(
        "app.services.revenue_portfolio_service.revenue_identity_reconciliation_service.reconcile",
        return_value={
            "status": "reconciled",
            "identity": {
                "content_id": "c4",
                "publication_id": "p4",
                "execution_key": "e4",
                "transactions": [{"amount": 125}],
            },
        },
    ) as reconcile:
        result = revenue_portfolio_service.aggregate(
            organization_id=1,
            content_results=[{
                "organization_id": 1,
                "content_id": "c4",
                "publication": {"channel": "telegram", "publication_id": "p4"},
                "execution_key": "e4",
                "reconciliation": {"status": "reconciled"},
                "payment_evidence": [{"provider_transaction_id": "real-tx"}],
                "provider_measurement": {"verified": True, "metric_evidence_digest": "m4"},
                "commercial": {"revenue": {"amount": 9999}, "economics": {"qualified_views": 1000}},
            }],
        )
    reconcile.assert_called_once()
    assert result["portfolio"]["verified_revenue"] == 125
    assert result["records"][0]["revenue_amount_source"] == "reconciled_payment_transactions"


def test_unreconciled_payment_evidence_cannot_be_overridden_by_claimed_reconciliation():
    from unittest.mock import patch

    with patch(
        "app.services.revenue_portfolio_service.revenue_identity_reconciliation_service.reconcile",
        return_value={"status": "not_reconciled", "identity": {}},
    ):
        result = revenue_portfolio_service.aggregate(
            organization_id=1,
            content_results=[{
                "organization_id": 1,
                "content_id": "c5",
                "publication": {"channel": "telegram", "publication_id": "p5"},
                "execution_key": "e5",
                "reconciliation": {"status": "reconciled"},
                "payment_evidence": [{"provider_transaction_id": "bad-tx"}],
                "provider_measurement": {"verified": True, "metric_evidence_digest": "m5"},
                "commercial": {"revenue": {"amount": 9999}, "economics": {"qualified_views": 1000}},
            }],
        )
    assert result["portfolio"]["verified_revenue"] == 0
    assert result["records"][0]["eligible"] is False
