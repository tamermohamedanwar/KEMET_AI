import hashlib
import hmac
import json

from wsgi import application


def _client():
    application.config["WTF_CSRF_ENABLED"] = False
    return application.test_client()


def test_telegram_webhook_rejects_missing_provider_secret(monkeypatch):
    monkeypatch.setenv("KEMET_TELEGRAM_WEBHOOK_SECRET", "telegram-secret")
    client = _client()
    response = client.post("/api/bos/channels/telegram/webhook/1", json={"message": {"message_id": 901, "from": {"id": 17}, "chat": {"id": 21}, "text": "hello"}})
    assert response.status_code == 403
    assert response.get_json()["error"] == "webhook_authentication_failed"


def test_telegram_webhook_is_verified_and_deduplicated(monkeypatch):
    monkeypatch.setenv("KEMET_TELEGRAM_WEBHOOK_SECRET", "telegram-secret")
    client = _client()
    payload = {
        "update_id": 992000902,
        "message": {
            "message_id": 902,
            "from": {"id": 18},
            "chat": {"id": 22},
            "text": "hello",
        },
    }
    headers = {"X-Telegram-Bot-Api-Secret-Token": "telegram-secret"}
    first = client.post("/api/bos/channels/telegram/webhook/1", json=payload, headers=headers)
    second = client.post("/api/bos/channels/telegram/webhook/1", json=payload, headers=headers)
    assert first.status_code == 200, first.get_json()
    assert first.get_json()["accepted"][0]["ingress"]["status"] == "accepted_no_match"
    assert second.status_code == 200, second.get_json()
    assert second.get_json()["accepted"][0]["status"] == "deduplicated"


def test_telegram_video_inquiry_creates_owner_notification(monkeypatch):
    monkeypatch.setenv("KEMET_TELEGRAM_WEBHOOK_SECRET", "telegram-secret")
    client = _client()
    payload = {"message": {"message_id": 904, "from": {"id": 19}, "chat": {"id": 23}, "text": "عايز فيديو إعلاني لشركتي"}}
    headers = {"X-Telegram-Bot-Api-Secret-Token": "telegram-secret"}
    response = client.post("/api/bos/channels/telegram/webhook/1", json=payload, headers=headers)
    assert response.status_code == 200, response.get_json()
    result = response.get_json()["accepted"][0]["owner_notification"]
    assert result["notified"] is True
    assert result["notification"]["title"] == "Kemet — New Video Lead"


def test_whatsapp_webhook_rejects_invalid_signature(monkeypatch):
    monkeypatch.setenv("KEMET_META_APP_SECRET", "meta-secret")
    client = _client()
    response = client.post("/api/bos/channels/whatsapp/webhook/1", data=b'{"entry":[]}', headers={"X-Hub-Signature-256": "sha256=wrong"}, content_type="application/json")
    assert response.status_code == 403


def test_whatsapp_webhook_accepts_valid_signature(monkeypatch):
    secret = "meta-secret"
    monkeypatch.setenv("KEMET_META_APP_SECRET", secret)
    client = _client()
    body = json.dumps({"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "p1"}, "messages": [{"id": "wa-903", "from": "u1", "type": "text", "text": {"body": "hello"}}]}}]}]}).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    response = client.post("/api/bos/channels/whatsapp/webhook/1", data=body, headers={"X-Hub-Signature-256": f"sha256={signature}"}, content_type="application/json")
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["accepted"][0]["request"]["channel"] == "whatsapp"


def test_whatsapp_identity_starts_shared_commercial_qualification(monkeypatch):
    secret = "meta-secret"
    monkeypatch.setenv("KEMET_META_APP_SECRET", secret)
    client = _client()
    body = json.dumps({"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "p2"}, "messages": [{"id": "wa-9101", "from": "u9101", "type": "text", "text": {"body": "company: Demo Co + email: demo9101@example.com"}}]}}]}]}).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    response = client.post("/api/bos/channels/whatsapp/webhook/1", data=body, headers={"X-Hub-Signature-256": f"sha256={signature}"}, content_type="application/json")
    assert response.status_code == 200, response.get_json()
    item = response.get_json()["accepted"][0]
    assert item["lead_intake"] == "created_or_existing"
    assert item["qualification"]["status"] == "qualification_in_progress"
    assert item["qualification"]["next_field"] == "desired_service"
    assert item["whatsapp_response_plan"]["operation"] == "send_text"
    assert item["whatsapp_response_plan"]["delivery"] == "approval_required"


def test_whatsapp_answer_advances_shared_qualification(monkeypatch):
    secret = "meta-secret"
    monkeypatch.setenv("KEMET_META_APP_SECRET", secret)
    client = _client()

    identity_body = json.dumps({"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "p3"}, "messages": [{"id": "wa-9201", "from": "u9201", "type": "text", "text": {"body": "company: Answer Co + email: answer9201@example.com"}}]}}]}]}).encode()
    identity_signature = hmac.new(secret.encode(), identity_body, hashlib.sha256).hexdigest()
    identity_response = client.post("/api/bos/channels/whatsapp/webhook/1", data=identity_body, headers={"X-Hub-Signature-256": f"sha256={identity_signature}"}, content_type="application/json")
    assert identity_response.status_code == 200, identity_response.get_json()

    body = json.dumps({"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "p3"}, "messages": [{"id": "wa-9202", "from": "u9201", "type": "text", "text": {"body": "تحويل الفواتير إلى Excel وCSV"}}]}}]}]}).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    response = client.post("/api/bos/channels/whatsapp/webhook/1", data=body, headers={"X-Hub-Signature-256": f"sha256={signature}"}, content_type="application/json")
    assert response.status_code == 200, response.get_json()
    item = response.get_json()["accepted"][0]
    assert item["qualification"]["status"] == "qualification_in_progress"
    assert item["qualification"]["next_field"] == "business_need"
    assert item["qualification"]["response_plan"]["channel"] == "whatsapp"

def test_whatsapp_without_identity_uses_canonical_catalog_response_plan(monkeypatch):
    secret = "meta-secret"
    monkeypatch.setenv("KEMET_META_APP_SECRET", secret)
    client = _client()
    body = json.dumps({"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "p4"}, "messages": [{"id": "wa-9301", "from": "u9301", "type": "text", "text": {"body": "مرحبا"}}]}}]}]}).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    response = client.post("/api/bos/channels/whatsapp/webhook/1", data=body, headers={"X-Hub-Signature-256": f"sha256={signature}"}, content_type="application/json")
    assert response.status_code == 200, response.get_json()
    plan = response.get_json()["accepted"][0]["whatsapp_response_plan"]
    assert plan["operation"] == "send_text"
    assert plan["delivery"] == "approval_required"
    assert "💼 الوظائف | Jobs" in plan["payload"]["text"]["body"]
    assert "📦 أدوات الأعمال | Business Tools" in plan["payload"]["text"]["body"]
    assert plan["governance"]["external_execution"] is False
