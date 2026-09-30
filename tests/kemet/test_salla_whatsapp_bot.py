import json

from app import create_app


def _app():
    app = create_app()
    app.config.update(TESTING=True)
    return app


def test_salla_whatsapp_bot_rejects_invalid_signature(monkeypatch):
    app = _app()
    monkeypatch.setattr(
        "app.routes.salla_whatsapp_bot.salla_connector_service.verify_webhook",
        lambda **kwargs: False,
    )
    client = app.test_client()
    response = client.post(
        "/salla-whatsapp-bot/webhook/1",
        json={"event": "order.created", "data": {"id": "1", "customer": {"phone": "201000000000"}}},
    )
    assert response.status_code == 403


def test_salla_whatsapp_bot_normalizes_and_uses_governed_product_path(monkeypatch):
    app = _app()
    monkeypatch.setattr(
        "app.routes.salla_whatsapp_bot.salla_connector_service.verify_webhook",
        lambda **kwargs: True,
    )
    monkeypatch.setattr(
        "app.routes.salla_whatsapp_bot.salla_whatsapp_product_service.prepare_order_notification",
        lambda **kwargs: {
            "success": True,
            "status": "approval_required",
            "approval_id": 42,
        },
    )
    monkeypatch.setattr(
        "app.routes.salla_whatsapp_bot.resolve_secret",
        lambda *args, **kwargs: "phone-1",
    )
    client = app.test_client()
    response = client.post(
        "/salla-whatsapp-bot/webhook/1",
        json={
            "event": "order.created",
            "data": {
                "id": "order-1",
                "status": "processing",
                "customer": {"phone": "201000000000"},
            },
        },
    )
    assert response.status_code == 202
    body = response.get_json()
    assert body["status"] == "approval_required"
    assert body["product"] == "salla_whatsapp_bot"


def test_customer_reply_requires_meta_signature(monkeypatch):
    app = _app()
    monkeypatch.setattr(
        "app.routes.salla_whatsapp_bot.channel_webhook_service.verify_meta_signature",
        lambda **kwargs: False,
    )
    client = app.test_client()
    payload = {"entry": []}
    response = client.post(
        "/salla-whatsapp-bot/whatsapp/webhook/1",
        data=json.dumps(payload),
        content_type="application/json",
        headers={"X-Hub-Signature-256": "sha256=invalid"},
    )
    assert response.status_code == 403
