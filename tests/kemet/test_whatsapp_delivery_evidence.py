import hashlib
import hmac
import json

from wsgi import application


def _client():
    application.config["WTF_CSRF_ENABLED"] = False
    return application.test_client()


def test_meta_delivery_status_is_durable_and_idempotent(monkeypatch):
    secret = "meta-secret"
    monkeypatch.setenv("KEMET_META_APP_SECRET", secret)
    client = _client()
    body = json.dumps({"entry": [{"changes": [{"value": {"metadata": {"phone_number_id": "p1"}, "statuses": [{"id": "wamid.delivery.1", "status": "delivered", "recipient_id": "201000000000", "timestamp": "1770000000"}]}}]}]}).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    headers = {"X-Hub-Signature-256": f"sha256={signature}"}
    first = client.post("/api/bos/channels/whatsapp/webhook/1", data=body, headers=headers, content_type="application/json")
    second = client.post("/api/bos/channels/whatsapp/webhook/1", data=body, headers=headers, content_type="application/json")
    assert first.status_code == 200, first.get_json()
    assert first.get_json()["accepted"][0]["delivery"]["status"] == "delivered"
    assert first.get_json()["accepted"][0]["ingress"]["status"] == "accepted_no_match"
    assert second.status_code == 200, second.get_json()
    assert second.get_json()["accepted"][0]["status"] == "deduplicated"


def test_meta_failed_delivery_is_ingested_without_execution(monkeypatch):
    secret = "meta-secret"
    monkeypatch.setenv("KEMET_META_APP_SECRET", secret)
    client = _client()
    body = json.dumps({"entry": [{"changes": [{"value": {"statuses": [{"id": "wamid.failed.1", "status": "failed", "recipient_id": "201000000000", "errors": [{"code": 131000}]}]}}]}]}).encode()
    signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    response = client.post("/api/bos/channels/whatsapp/webhook/1", data=body, headers={"X-Hub-Signature-256": f"sha256={signature}"}, content_type="application/json")
    assert response.status_code == 200, response.get_json()
    result = response.get_json()["accepted"][0]
    assert result["delivery"]["status"] == "failed"
    assert result["delivery"]["governance"]["external_execution"] is False


def test_delivery_status_binds_to_existing_whatsapp_execution_evidence():
    from app import create_app, db
    from app.core.execution_evidence import execution_evidence

    app = create_app()
    with app.app_context():
        execution_evidence.record(
            organization_id=1,
            execution_key="wa-exec-binding",
            job_id=9011,
            stage="channel.delivery",
            status="sent",
            evidence_key="wa-exec-binding:sent:wamid.binding",
            receipt={"provider": "meta_whatsapp_cloud", "message_id": "wamid.binding"},
        )
        from app.services.whatsapp_delivery_evidence_service import whatsapp_delivery_evidence_service
        binding = whatsapp_delivery_evidence_service.record_delivery(
            organization_id=1,
            message_id="wamid.binding",
            status="delivered",
        )
        db.session.commit()

    assert binding["execution_key"] == "wa-exec-binding"
    assert binding["job_id"] == 9011
