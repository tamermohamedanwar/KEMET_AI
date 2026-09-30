from app.services.revenue_content_decision_signal_service import revenue_content_decision_signal_service


def test_builds_reviewable_signal_only_for_reconciled_content():
    result = revenue_content_decision_signal_service.build(
        organization_id=1,
        intelligence={
            "signals": {"verified_revenue": 125, "verified_content_count": 1, "authoritatively_measured_content_count": 1, "revenue_per_1000_qualified_views": 25},
            "records": [
                {"content_id": "c1", "channel": "facebook", "publication_id": "p1", "execution_key": "e1", "reconciliation": {"status": "reconciled"}, "verified_measurement": True, "verified_revenue_amount": 125, "qualified_views": 5000},
                {"content_id": "c2", "channel": "instagram", "reconciliation": {"status": "not_reconciled"}, "verified_measurement": True, "verified_revenue_amount": 999, "qualified_views": 1000},
            ],
        },
    )
    assert result["records"][0]["decision_readiness"] == "reviewable"
    assert result["records"][0]["verified_revenue"] == 125
    assert result["records"][1]["decision_readiness"] == "evidence_incomplete"
    assert result["records"][1]["verified_revenue"] is None
    assert result["decision_support"]["automatic_action"] is False


def test_recomputes_aggregate_signals_from_reviewable_records():
    result = revenue_content_decision_signal_service.build(
        organization_id=1,
        intelligence={
            "signals": {"verified_revenue": 999999, "verified_content_count": 99},
            "records": [
                {"content_id": "c1", "channel": "facebook", "publication_id": "p1", "execution_key": "e1", "reconciliation": {"status": "reconciled"}, "verified_measurement": True, "verified_revenue_amount": 125, "qualified_views": 5000},
                {"content_id": "c2", "channel": "instagram", "publication_id": "p2", "execution_key": "e2", "reconciliation": {"status": "reconciled"}, "verified_measurement": False, "verified_revenue_amount": 900, "qualified_views": 9000},
            ],
        },
    )
    assert result["signals"]["verified_revenue"] == 125
    assert result["signals"]["verified_content_count"] == 1
    assert result["signals"]["authoritatively_measured_content_count"] == 1


def test_rejects_invalid_organization():
    try:
        revenue_content_decision_signal_service.build(organization_id=0)
    except ValueError as exc:
        assert str(exc) == "organization_required"
    else:
        raise AssertionError("expected organization_required")



def test_payment_evidence_reconciliation_overrides_untrusted_status():
    from app import create_app, db
    from app.models.payment import Payment
    import uuid

    app = create_app()
    with app.app_context():
        tx = f"tx-{uuid.uuid4().hex}"
        payment = Payment(
            organization_id=1, plan="business", amount=125, currency="USD",
            status="paid", provider="paymob", provider_transaction_id=tx,
        )
        db.session.add(payment)
        db.session.flush()
        result = revenue_content_decision_signal_service.build(
            organization_id=1,
            intelligence={"records": [{
                "content_id": "c1", "channel": "telegram", "publication_id": "p1",
                "execution_key": "e1",
                "reconciliation": {"status": "reconciled"},
                "verified_measurement": True, "verified_revenue_amount": 125, "qualified_views": 1000,
                "payment_evidence": [{
                    "stage": "payment.completed",
                    "receipt": {
                        "content_id": "c1", "publication_id": "p1",
                        "payment_id": payment.id,
                        "provider_transaction_id": "wrong-tx",
                    },
                }],
            }]},
        )
        db.session.delete(payment)
        db.session.commit()
    assert result["records"][0]["reconciliation_status"] == "not_reconciled"
    assert result["records"][0]["decision_readiness"] == "evidence_incomplete"
    assert result["signals"]["verified_revenue"] == 0.0


def test_reconciled_payment_amount_is_authoritative():
    from app import create_app, db
    from app.models.payment import Payment
    import uuid
    app = create_app()
    with app.app_context():
        tx = f"tx-{uuid.uuid4().hex}"
        payment = Payment(organization_id=1, plan="business", amount=125, currency="USD", status="paid", provider="paymob", provider_transaction_id=tx)
        db.session.add(payment); db.session.flush()
        result = revenue_content_decision_signal_service.build(organization_id=1, intelligence={"records": [{
            "content_id": "c1", "channel": "telegram", "publication_id": "p1", "execution_key": "e1",
            "verified_measurement": True, "verified_revenue_amount": 9999, "qualified_views": 1000,
            "payment_evidence": [{"stage": "payment.completed", "receipt": {"content_id": "c1", "publication_id": "p1", "payment_id": payment.id, "provider_transaction_id": tx}}],
        }]})
        db.session.delete(payment); db.session.commit()
    assert result["signals"]["verified_revenue"] == 125.0
