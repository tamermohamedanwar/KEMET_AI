import os

from cryptography.fernet import Fernet, InvalidToken


_ENV_NAME = "KEMET_PAYMENT_ENCRYPTION_KEY"
_PREFIX = "v1:"


def _fernet():
    raw = os.getenv(_ENV_NAME, "").strip()
    if not raw:
        raise RuntimeError("payment_encryption_key_not_configured")
    try:
        return Fernet(raw.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("payment_encryption_key_invalid") from exc


def encrypt_payment_token(value: str) -> str:
    token = str(value or "").strip()
    if not token:
        raise ValueError("payment_token_required")
    return _PREFIX + _fernet().encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_payment_token(value: str) -> str:
    stored = str(value or "").strip()
    if not stored:
        return ""
    if not stored.startswith(_PREFIX):
        return stored
    try:
        return _fernet().decrypt(stored[len(_PREFIX):].encode("utf-8")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError, TypeError) as exc:
        raise RuntimeError("payment_token_decryption_failed") from exc


def get_payment_token(payment) -> str:
    encrypted = getattr(payment, "client_secret_encrypted", None)
    if encrypted:
        return decrypt_payment_token(encrypted)
    return decrypt_payment_token(getattr(payment, "client_secret", None))
