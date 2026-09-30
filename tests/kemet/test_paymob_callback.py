import hashlib
import hmac
import json
from uuid import uuid4

from app import create_app, db
from app.models.payment import Payment


def _payload(order_id, transaction_id, *, amount=12500, currency="EGP"):
    obj = {
        "amount_cents": amount,
        "created_at": "2026-09-15T20:00:00Z",
        "currency": currency,
        "error_occured": False,
        "has_parent_transaction": False,
        "id": transaction_id,
        "integration_id": 123,
        "is_3d_secure": False,
        "is_auth": True,
        "is_capture": True,
        "is_refunded": False,
        "is_standalone_payment": False,
        "is_voided": False,
        "order": {"id": order_id},
        "owner": 1,
        "pending": False,
        "source_data": {"pan": "2346", "sub_type": "Visa", "type": "card"},
        "success": True,
    }
    return {"obj": obj}, obj


def _signed_query(obj, secret):
    order = obj["order"]
    source_data = obj["source_data"]
    values = [
        obj.get("amount_cents"), obj.get("created_at"), obj.get("currency"), obj.get("error_occured"),
        obj.get("has_parent_transaction"), obj.get("id"), obj.get("integration_id"),
        obj.get("is_3d_secure"), obj.get("is_auth"), obj.get("is_capture"), obj.get("is_refunded"),
        obj.get("is_standalone_payment"), obj.get("is_voided"), order, obj.get("owner"),
        obj.get("pending"), source_data.get("pan"), source_data.get("sub_type"),
        source_data.get("type"), obj.get("success"),
    ]
    def value(item):
        if item is None:
            return ""
        if isinstance(item, bool):
            return "true" if item else "false"
        if isinstance(item, dict):
            return str(item["id"]) if "id" in item else ""
        return str(item)
    message = "".join(value(item) for item in values)
    return hmac.new(secret.encode(), message.encode(), hashlib.sha512).hexdigest()


def _client_and_payment(monkeypatch, **kwargs):
    secret = "callback-secret"
    monkeypatch.setenv("PAYMOB_HMAC_SECRET", secret)
    monkeypatch.setenv("PAYMOB_INTEGRATION_ID", "123")
    app = create_app()
    order_id = str(kwargs.pop("order_id", f"order-{uuid4().hex}"))
    transaction_id = str(kwargs.pop("transaction_id", f"tx-{uuid4().hex}"))
    payment = Payment(
        organization_id=1, plan="business", amount=125, currency="EGP",
        status="pending", provider=kwargs.pop("provider", "paymob"),
        checkout_id=order_id, provider_order_id=kwargs.pop("provider_order_id", order_id),
        provider_transaction_id=kwargs.pop("provider_transaction_id", None),
    )
    with app.app_context():
        db.session.add(payment)
        db.session.commit()
        payload, obj = _payload(order_id, transaction_id)
        payload["hmac"] = _signed_query(obj, secret)
        return app, payment.id, payload


def test_paymob_callback_rejects_provider_mismatch(monkeypatch):
    app, payment_id, payload = _client_and_payment(monkeypatch, provider="mock")
    with app.test_client() as client:
        response = client.post("/payment/paymob/callback", json=payload, query_string={"hmac": payload["hmac"]})
    assert response.status_code == 409
    assert response.get_json()["status"] == "payment_provider_mismatch"
    with app.app_context():
        db.session.delete(db.session.get(Payment, payment_id))
        db.session.commit()


def test_paymob_callback_rejects_provider_order_mismatch(monkeypatch):
    app, payment_id, payload = _client_and_payment(monkeypatch, provider_order_id="different-order")
    with app.test_client() as client:
        response = client.post("/payment/paymob/callback", json=payload, query_string={"hmac": payload["hmac"]})
    assert response.status_code == 409
    assert response.get_json()["status"] == "provider_order_mismatch"
    with app.app_context():
        db.session.delete(db.session.get(Payment, payment_id))
        db.session.commit()


def test_paymob_callback_rejects_provider_transaction_mismatch(monkeypatch):
    app, payment_id, payload = _client_and_payment(monkeypatch, provider_transaction_id="different-tx")
    with app.test_client() as client:
        response = client.post("/payment/paymob/callback", json=payload, query_string={"hmac": payload["hmac"]})
    assert response.status_code == 409
    assert response.get_json()["status"] == "provider_transaction_mismatch"
    with app.app_context():
        db.session.delete(db.session.get(Payment, payment_id))
        db.session.commit()


def test_paymob_callback_rejects_transaction_reuse(monkeypatch):
    app, payment_id, payload = _client_and_payment(monkeypatch)
    with app.app_context():
        conflict = Payment(
            organization_id=1, plan="business", amount=125, currency="EGP",
            status="pending", provider="paymob", provider_transaction_id=payload["obj"]["id"],
        )
        db.session.add(conflict)
        db.session.commit()
        conflict_id = conflict.id
    with app.test_client() as client:
        response = client.post("/payment/paymob/callback", json=payload, query_string={"hmac": payload["hmac"]})
    assert response.status_code == 409
    assert response.get_json()["status"] == "provider_transaction_conflict"
    with app.app_context():
        db.session.delete(db.session.get(Payment, payment_id))
        db.session.delete(db.session.get(Payment, conflict_id))
        db.session.commit()


def test_paymob_callback_rejects_missing_integration_configuration(monkeypatch):
    app, payment_id, payload = _client_and_payment(monkeypatch)
    monkeypatch.delenv("PAYMOB_INTEGRATION_ID", raising=False)
    with app.test_client() as client:
        response = client.post("/payment/paymob/callback", json=payload, query_string={"hmac": payload["hmac"]})
    assert response.status_code == 503
    assert response.get_json()["status"] == "integration_not_configured"
    with app.app_context():
        payment = db.session.get(Payment, payment_id)
        assert payment.status == "pending"
        assert payment.provider_transaction_id is None
        db.session.delete(payment)
        db.session.commit()


def test_paymob_callback_rejects_missing_callback_integration_id(monkeypatch):
    app, payment_id, payload = _client_and_payment(monkeypatch)
    payload["obj"].pop("integration_id")
    payload["hmac"] = _signed_query(payload["obj"], "callback-secret")
    with app.test_client() as client:
        response = client.post("/payment/paymob/callback", json=payload, query_string={"hmac": payload["hmac"]})
    assert response.status_code == 409
    assert response.get_json()["status"] == "integration_mismatch"
    with app.app_context():
        payment = db.session.get(Payment, payment_id)
        assert payment.status == "pending"
        assert payment.provider_transaction_id is None
        db.session.delete(payment)
        db.session.commit()


def test_paymob_callback_rejects_amount_mismatch_without_mutation(monkeypatch):
    app, payment_id, payload = _client_and_payment(monkeypatch)
    payload["obj"]["amount_cents"] = 1
    secret = "callback-secret"
    payload["hmac"] = _signed_query(payload["obj"], secret)
    with app.test_client() as client:
        response = client.post("/payment/paymob/callback", json=payload, query_string={"hmac": payload["hmac"]})
    assert response.status_code == 200
    assert response.get_json()["status"] == "failed"
    with app.app_context():
        payment = db.session.get(Payment, payment_id)
        assert payment.status == "failed"
        assert payment.provider_transaction_id == payload["obj"]["id"]
        db.session.delete(payment)
        db.session.commit()
