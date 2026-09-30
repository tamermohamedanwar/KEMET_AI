from app.services.revenue_center_evidence_service import RevenueCenterEvidenceService


def test_revenue_center_aggregates_only_verified_content_revenue():
    result = RevenueCenterEvidenceService.summarize(
        organization_id=7,
        content_results=[
            {
                "organization_id": 7,
                "content_id": "c1",
                "publication": {
                    "publication_id": "p1",
                    "channel": "facebook",
                    "evidence_digest": "d1",
                },
                "provider_measurement": {"verified": True},
                "commercial": {
                    "revenue": {
                        "amount": 500,
                        "currency": "EGP",
                        "evidence_backed": True,
                    }
                },
            },
            {
                "organization_id": 7,
                "content_id": "c2",
                "publication": {"publication_id": "p2", "channel": "instagram"},
                "provider_measurement": {"verified": True},
                "commercial": {
                    "revenue": {
                        "amount": 999999,
                        "evidence_backed": False,
                    }
                },
            },
        ],
    )
    assert result["verified_content_revenue"] == 500.0
    assert result["verified_content_count"] == 1
    assert result["authoritatively_measured_content_count"] == 2
    assert result["measurement"]["forecast_is_not_recorded_revenue"] is True


def test_revenue_center_is_tenant_scoped_and_read_only():
    result = RevenueCenterEvidenceService.summarize(42, [])
    assert result["organization_id"] == 42
    assert result["records"] == []
    assert result["governance"]["read_only"] is True
    assert result["governance"]["external_execution"] is False
    assert result["governance"]["execution_authority"] is False


def test_revenue_center_rejects_unknown_tenant():
    import pytest

    with pytest.raises(ValueError, match="organization_required"):
        RevenueCenterEvidenceService.summarize(0)


def test_revenue_center_uses_reconciled_payment_amount_when_evidence_exists():
    from app import create_app, db
    from app.models.payment import Payment
    import uuid
    app = create_app()
    with app.app_context():
        tx = f"tx-{uuid.uuid4().hex}"
        payment = Payment(organization_id=7, plan="business", amount=125, currency="EGP", status="paid", provider="paymob", provider_transaction_id=tx)
        db.session.add(payment); db.session.flush()
        result = RevenueCenterEvidenceService.summarize(7, [{
            "organization_id": 7, "content_id": "c1",
            "publication": {"publication_id": "p1", "channel": "telegram"},
            "provider_measurement": {"verified": True},
            "commercial": {"revenue": {"amount": 9999, "currency": "EGP", "evidence_backed": True}},
            "execution_key": "e1",
            "payment_evidence": [{"stage": "payment.completed", "receipt": {"content_id": "c1", "publication_id": "p1", "execution_key": "e1", "organization_id": 7, "payment_id": payment.id, "provider_transaction_id": tx, "amount": 9999}}],
        }])
        db.session.delete(payment); db.session.commit()
    assert result["verified_content_revenue"] == 125.0
    assert result["records"][0]["revenue_amount"] == 125.0


def test_revenue_center_rejects_conflicting_payment_identity():
    from app import create_app, db
    from app.models.payment import Payment
    import uuid
    app = create_app()
    with app.app_context():
        payment = Payment(organization_id=7, plan="business", amount=125, currency="EGP", status="paid", provider="paymob", provider_transaction_id=f"tx-{uuid.uuid4().hex}")
        db.session.add(payment); db.session.flush()
        result = RevenueCenterEvidenceService.summarize(7, [{
            "organization_id": 7, "content_id": "c1", "publication": {"publication_id": "p1", "channel": "telegram"},
            "provider_measurement": {"verified": True}, "commercial": {"revenue": {"amount": 9999, "evidence_backed": True}}, "execution_key": "e1",
            "payment_evidence": [{"stage": "payment.completed", "receipt": {"content_id": "c1", "publication_id": "p1", "execution_key": "e1", "organization_id": 7, "payment_id": payment.id, "provider_transaction_id": "wrong"}}],
        }])
        db.session.delete(payment); db.session.commit()
    assert result["verified_content_revenue"] == 0.0
    assert result["verified_content_count"] == 0
