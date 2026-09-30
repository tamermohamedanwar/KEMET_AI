import hashlib
import hmac
import json

from app.services.channel_webhook_service import channel_webhook_service


def test_telegram_secret_verification(monkeypatch):
    monkeypatch.setenv("KEMET_TELEGRAM_WEBHOOK_SECRET", "telegram-secret")
    assert channel_webhook_service.verify_telegram(secret_token="telegram-secret") is True
    assert channel_webhook_service.verify_telegram(secret_token="wrong") is False


def test_meta_signature_verification(monkeypatch):
    secret = "meta-secret"
    body = json.dumps({"entry": []}).encode()
    monkeypatch.setenv("KEMET_META_APP_SECRET", secret)
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert channel_webhook_service.verify_meta_signature(raw_body=body, signature=f"sha256={digest}") is True
    assert channel_webhook_service.verify_meta_signature(raw_body=body, signature="sha256=wrong") is False


def test_meta_challenge_verification(monkeypatch):
    monkeypatch.setenv("KEMET_META_VERIFY_TOKEN", "verify-secret")
    assert channel_webhook_service.verify_meta_challenge(verify_token="verify-secret", challenge="123") is True
    assert channel_webhook_service.verify_meta_challenge(verify_token="wrong", challenge="123") is False


def test_telegram_extraction_is_provider_boundary_only():
    result = channel_webhook_service.extract_telegram({"message": {"message_id": 9, "from": {"id": 17}, "chat": {"id": 21}, "text": "hello"}})
    assert result["external_message_id"] == "9"
    assert result["external_user_id"] == "17"
    assert result["conversation_id"] == "21"
    assert result["text"] == "hello"


def test_meta_extraction_supports_text_messages():
    result = channel_webhook_service.extract_meta({"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "p1"}, "messages": [{"id": "m1", "from": "u1", "type": "text", "text": {"body": "hello"}}]}}]}]})
    assert len(result) == 1
    assert result[0]["external_message_id"] == "m1"
    assert result[0]["external_user_id"] == "u1"
    assert result[0]["text"] == "hello"


def test_extract_telegram_commercial_identity_compact_arabic_message():
    text = "اسم الشركة: Kemet_AI البريد الإلكتروني: Tamer.mohamed.anwar@gmail.com"
    identity = channel_webhook_service.extract_telegram_commercial_identity(text)
    assert identity == {"company_name": "Kemet_AI", "email": "tamer.mohamed.anwar@gmail.com"}
