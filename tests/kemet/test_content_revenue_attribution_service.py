import pytest

from app.services.content_revenue_attribution_service import (
    content_revenue_attribution_service,
)


def test_content_revenue_uses_only_bound_verified_payment_evidence():
    result = content_revenue_attribution_service.evaluate(
        content_id="episode-1",
        metrics={"views": 10000, "qualified_views": 5000, "conversions": 2},
        payment_evidence=[
            {
                "stage": "payment.completed",
                "receipt": {
                    "payment_id": 10,
                    "content_id": "episode-1",
                    "amount": 125,
                    "currency": "EGP",
                    "provider_transaction_id": "tx-1",
                },
            },
            {
                "stage": "payment.completed",
                "receipt": {
                    "payment_id": 11,
                    "content_id": "other",
                    "amount": 999,
                    "currency": "EGP",
                    "provider_transaction_id": "tx-2",
                },
            },
        ],
    )
    assert result["revenue"]["amount"] == 125.0
    assert result["revenue"]["verified_payment_count"] == 1
    assert result["revenue"]["evidence_backed"] is True
    assert result["economics"]["revenue_per_1000_qualified_views"] == 25.0
    assert result["attribution"]["causal_claim"] is False
    assert result["attribution"]["roi_claim"] is False
    assert result["governance"]["execution_authority"] is False


def test_content_revenue_fails_closed_without_verified_payment_evidence():
    result = content_revenue_attribution_service.evaluate(
        content_id="episode-2",
        metrics={"views": 1000, "qualified_views": 500},
        payment_evidence=[
            {
                "stage": "payment.completed",
                "receipt": {
                    "content_id": "episode-2",
                    "amount": 100,
                    "currency": "EGP",
                },
            }
        ],
    )
    assert result["revenue"]["amount"] == 0.0
    assert result["revenue"]["evidence_backed"] is False
    assert result["economics"]["revenue_per_1000_qualified_views"] is None
    assert result["attribution"]["source"] == "not_available"


def test_content_revenue_rejects_invalid_metrics():
    with pytest.raises(ValueError, match="negative_metric:qualified_views"):
        content_revenue_attribution_service.evaluate(
            content_id="episode-3",
            metrics={"qualified_views": -1},
        )


def test_content_revenue_uses_reconciled_payment_amount_when_identity_context_exists():
    from app import create_app, db
    from app.models.payment import Payment
    import uuid
    app = create_app()
    with app.app_context():
        tx = f"tx-{uuid.uuid4().hex}"
        payment = Payment(organization_id=42, plan="business", amount=125, currency="EGP", status="paid", provider="paymob", provider_transaction_id=tx)
        db.session.add(payment); db.session.flush()
        result = content_revenue_attribution_service.evaluate(
            content_id="episode-identity", metrics={"qualified_views": 5000}, organization_id=42, publication_id="pub-1", execution_key="exec-1",
            payment_evidence=[{"stage":"payment.completed", "receipt":{"content_id":"episode-identity","publication_id":"pub-1","execution_key":"exec-1","organization_id":42,"payment_id":payment.id,"amount":9999,"currency":"EGP","provider_transaction_id":tx}}],
        )
        db.session.delete(payment); db.session.commit()
    assert result["revenue"]["amount"] == 125.0


def test_content_revenue_rejects_conflicting_identity_when_context_exists():
    from app import create_app, db
    from app.models.payment import Payment
    import uuid
    app = create_app()
    with app.app_context():
        tx = f"tx-{uuid.uuid4().hex}"
        payment = Payment(organization_id=42, plan="business", amount=125, currency="EGP", status="paid", provider="paymob", provider_transaction_id=tx)
        db.session.add(payment); db.session.flush()
        result = content_revenue_attribution_service.evaluate(
            content_id="episode-conflict", metrics={"qualified_views": 5000}, organization_id=42, publication_id="pub-1", execution_key="exec-1",
            payment_evidence=[{"stage":"payment.completed", "receipt":{"content_id":"episode-conflict","publication_id":"pub-1","execution_key":"exec-1","organization_id":42,"payment_id":payment.id,"amount":125,"currency":"EGP","provider_transaction_id":"wrong-tx"}}],
        )
        db.session.delete(payment); db.session.commit()
    assert result["revenue"]["amount"] == 0.0
    assert result["revenue"]["evidence_backed"] is False
