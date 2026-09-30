from app.services.revenue_intelligence_service import RevenueIntelligenceService


def test_revenue_intelligence_uses_verified_revenue_only():
    result = RevenueIntelligenceService.analyze(
        organization_id=42,
        content_results=[
            {
                "organization_id": 42,
                "content_id": "c1",
                "publication": {"channel": "facebook"},
                "provider_measurement": {"verified": True, "metric_evidence_digest": "md1"},
                "reconciliation": {"status": "reconciled"},
                "execution_key": "exec-c1",
                "commercial": {"revenue": {"amount": 125, "evidence_backed": True}, "economics": {"qualified_views": 5000}},
            },
            {
                "organization_id": 42,
                "content_id": "c2",
                "publication": {"channel": "instagram"},
                "provider_measurement": {"verified": True},
                "reconciliation": {"status": "not_reconciled"},
                "commercial": {"revenue": {"amount": 999999, "evidence_backed": False}, "economics": {"qualified_views": 9000}},
            },
        ],
    )
    assert result["signals"]["verified_revenue"] == 125.0
    assert result["signals"]["verified_content_count"] == 1
    assert result["signals"]["authoritatively_measured_content_count"] == 2
    assert result["signals"]["revenue_per_1000_qualified_views"] == 25.0
    assert result["decision_support"]["no_automatic_action"] is True


def test_revenue_intelligence_is_tenant_scoped_and_fail_closed():
    import pytest
    with pytest.raises(ValueError, match="organization_required"):
        RevenueIntelligenceService.analyze(organization_id=0)


def test_revenue_intelligence_uses_reconciled_payment_amount_when_evidence_exists():
    from app import create_app, db
    from app.models.payment import Payment
    import uuid
    app = create_app()
    with app.app_context():
        tx = f"tx-{uuid.uuid4().hex}"
        payment = Payment(organization_id=42, plan="business", amount=125, currency="USD", status="paid", provider="paymob", provider_transaction_id=tx)
        db.session.add(payment); db.session.flush()
        result = RevenueIntelligenceService.analyze(organization_id=42, content_results=[{
            "organization_id": 42, "content_id": "c1", "publication": {"channel": "telegram", "publication_id": "p1"},
            "provider_measurement": {"verified": True}, "execution_key": "exec-c1",
            "commercial": {"revenue": {"amount": 9999, "evidence_backed": True}, "economics": {"qualified_views": 5000}},
            "payment_evidence": [{"stage": "payment.completed", "receipt": {"content_id": "c1", "publication_id": "p1", "payment_id": payment.id, "provider_transaction_id": tx}}],
        }])
        db.session.delete(payment); db.session.commit()
    assert result["signals"]["verified_revenue"] == 125.0
