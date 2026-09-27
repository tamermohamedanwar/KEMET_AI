from cryptography.fernet import Fernet
import pytest

from app.core.payment_secret import decrypt_payment_token, encrypt_payment_token


def test_payment_token_round_trip(monkeypatch):
    monkeypatch.setenv("KEMET_PAYMENT_ENCRYPTION_KEY", Fernet.generate_key().decode())
    encrypted = encrypt_payment_token("paymob-token-example")
    assert encrypted.startswith("v1:")
    assert encrypted != "paymob-token-example"
    assert decrypt_payment_token(encrypted) == "paymob-token-example"


def test_payment_token_requires_key(monkeypatch):
    monkeypatch.delenv("KEMET_PAYMENT_ENCRYPTION_KEY", raising=False)
    with pytest.raises(RuntimeError, match="payment_encryption_key_not_configured"):
        encrypt_payment_token("paymob-token-example")


def test_legacy_plaintext_is_read_for_backward_compatibility(monkeypatch):
    monkeypatch.setenv("KEMET_PAYMENT_ENCRYPTION_KEY", Fernet.generate_key().decode())
    assert decrypt_payment_token("legacy-paymob-token") == "legacy-paymob-token"
