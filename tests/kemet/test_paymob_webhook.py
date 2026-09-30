import hashlib
import hmac

from app.services.paymob_webhook import amount_cents, transaction_hmac, verify_transaction_callback


def _obj():
    return {
        "amount_cents": 12500,
        "created_at": "2026-09-15T20:00:00Z",
        "currency": "EGP",
        "error_occured": False,
        "has_parent_transaction": False,
        "id": 12345,
        "integration_id": 67890,
        "is_3d_secure": False,
        "is_auth": True,
        "is_capture": True,
        "is_refunded": False,
        "is_standalone_payment": False,
        "is_voided": False,
        "order": {"id": 98765},
        "owner": 1,
        "pending": False,
        "source_data": {"pan": "2346", "sub_type": "Visa", "type": "card"},
        "success": True,
    }


def test_transaction_hmac_matches_documented_field_order():
    obj = _obj()
    secret = "callback-secret"
    fields = [
        obj["amount_cents"], obj["created_at"], obj["currency"], obj["error_occured"],
        obj["has_parent_transaction"], obj["id"], obj["integration_id"], obj["is_3d_secure"],
        obj["is_auth"], obj["is_capture"], obj["is_refunded"], obj["is_standalone_payment"],
        obj["is_voided"], obj["order"]["id"], obj["owner"], obj["pending"],
        obj["source_data"]["pan"], obj["source_data"]["sub_type"], obj["source_data"]["type"], obj["success"],
    ]
    message = "".join("true" if x is True else "false" if x is False else str(x) for x in fields)
    expected = hmac.new(secret.encode(), message.encode(), hashlib.sha512).hexdigest()
    assert transaction_hmac(obj, secret) == expected


def test_transaction_callback_verification_is_fail_closed():
    obj = _obj()
    signature = transaction_hmac(obj, "callback-secret")
    assert verify_transaction_callback(obj, signature, "callback-secret") is True
    assert verify_transaction_callback(obj, signature[:-1] + "0", "callback-secret") is False
    assert verify_transaction_callback(obj, signature, "") is False


def test_amount_cents_prefers_current_paymob_field():
    assert amount_cents({"amount_cents": 12500, "amount": 1}) == 12500
    assert amount_cents({"amount": 12500}) == 12500
    assert amount_cents({"amount_cents": "bad"}) is None
