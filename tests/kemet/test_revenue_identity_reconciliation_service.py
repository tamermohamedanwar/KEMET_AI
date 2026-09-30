import json
import uuid

from app import create_app, db
from app.models.payment import Payment
from app.services.revenue_identity_reconciliation_service import revenue_identity_reconciliation_service


def test_reconciliation_binds_execution_evidence_to_paid_transaction():
    app = create_app()
    with app.app_context():
        tx = f"tx-{uuid.uuid4().hex}"
        payment = Payment(
            organization_id=1, plan="business", amount=125, currency="USD",
            status="paid", provider="paymob", provider_transaction_id=tx,
        )
        db.session.add(payment)
        db.session.flush()
        evidence = [{
            "stage": "payment.completed",
            "receipt": {
                "content_id": "content-1",
                "publication_id": "pub-1",
                "payment_id": payment.id,
                "provider_transaction_id": tx,
            },
        }]
        result = revenue_identity_reconciliation_service.reconcile(
            organization_id=1, content_id="content-1", publication_id="pub-1",
            execution_key="exec-1", evidence=evidence,
        )
        db.session.delete(payment)
        db.session.commit()
    assert result["status"] == "reconciled"
    assert result["identity"]["payment_count"] == 1
    assert result["identity"]["transactions"][0]["provider_transaction_id"] == tx


def test_reconciliation_rejects_transaction_identity_mismatch():
    app = create_app()
    with app.app_context():
        payment = Payment(
            organization_id=1, plan="business", amount=125, currency="USD",
            status="paid", provider="paymob", provider_transaction_id=f"real-{uuid.uuid4().hex}",
        )
        db.session.add(payment)
        db.session.flush()
        result = revenue_identity_reconciliation_service.reconcile(
            organization_id=1, content_id="content-1", publication_id="pub-1",
            execution_key="exec-1", evidence=[{
                "stage": "payment.completed",
                "receipt": {
                    "content_id": "content-1", "publication_id": "pub-1",
                    "payment_id": payment.id, "provider_transaction_id": "fake-tx",
                },
            }],
        )
        db.session.delete(payment)
        db.session.commit()
    assert result["status"] == "not_reconciled"
    assert result["evidence"]["verified"] is False


def test_reconciliation_is_tenant_scoped():
    app = create_app()
    with app.app_context():
        payment = Payment(
            organization_id=2, plan="business", amount=125, currency="USD",
            status="paid", provider="paymob", provider_transaction_id=f"tx-{uuid.uuid4().hex}",
        )
        db.session.add(payment)
        db.session.flush()
        result = revenue_identity_reconciliation_service.reconcile(
            organization_id=1, content_id="content-1", publication_id="pub-1",
            execution_key="exec-1", evidence=[{
                "stage": "payment.completed",
                "receipt": {
                    "content_id": "content-1", "publication_id": "pub-1",
                    "payment_id": payment.id,
                    "provider_transaction_id": payment.provider_transaction_id,
                },
            }],
        )
        db.session.delete(payment)
        db.session.commit()
    assert result["status"] == "not_reconciled"


def test_reconciliation_rejects_cross_execution_payment_evidence():
    app = create_app()
    with app.app_context():
        tx = f"tx-{uuid.uuid4().hex}"
        payment = Payment(
            organization_id=1, plan="business", amount=125, currency="USD",
            status="paid", provider="paymob", provider_transaction_id=tx,
        )
        db.session.add(payment)
        db.session.flush()
        result = revenue_identity_reconciliation_service.reconcile(
            organization_id=1, content_id="content-1", publication_id="pub-1",
            execution_key="exec-current", evidence=[{
                "stage": "payment.completed",
                "execution_key": "exec-old",
                "organization_id": 1,
                "receipt": {
                    "content_id": "content-1", "publication_id": "pub-1",
                    "payment_id": payment.id, "provider_transaction_id": tx,
                },
            }],
        )
        db.session.delete(payment)
        db.session.commit()
    assert result["status"] == "not_reconciled"
    assert result["evidence"]["verified"] is False
