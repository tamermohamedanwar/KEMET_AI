"""Fail-closed Paymob transaction callback verification."""
from __future__ import annotations

import hashlib
import hmac
from typing import Any


TRANSACTION_HMAC_FIELDS = (
    "amount_cents",
    "created_at",
    "currency",
    "error_occured",
    "has_parent_transaction",
    "id",
    "integration_id",
    "is_3d_secure",
    "is_auth",
    "is_capture",
    "is_refunded",
    "is_standalone_payment",
    "is_voided",
    "order.id",
    "owner",
    "pending",
    "source_data.pan",
    "source_data.sub_type",
    "source_data.type",
    "success",
)


def _value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def _field_value(obj: dict[str, Any], field: str) -> Any:
    if field == "order.id":
        return (obj.get("order") or {}).get("id")
    if field.startswith("source_data."):
        return (obj.get("source_data") or {}).get(field.split(".", 1)[1])
    return obj.get(field)


def transaction_hmac(obj: dict[str, Any], secret: str) -> str:
    message = "".join(_value(_field_value(obj, field)) for field in TRANSACTION_HMAC_FIELDS)
    return hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha512).hexdigest()


def verify_transaction_callback(obj: dict[str, Any], received_hmac: str, secret: str) -> bool:
    if not secret or not received_hmac:
        return False
    expected = transaction_hmac(obj, secret)
    return hmac.compare_digest(expected, received_hmac.strip().lower())


def amount_cents(obj: dict[str, Any]) -> int | None:
    raw = obj.get("amount_cents")
    if raw is None:
        raw = obj.get("amount")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None
