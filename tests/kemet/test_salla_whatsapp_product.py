import uuid

import pytest
from cryptography.fernet import Fernet

from app import create_app, db
from app.core.secret_boundary import resolve_secret
from app.services.salla_whatsapp_product_service import SallaWhatsAppProductService


def test_product_credentials_are_encrypted_and_tenant_scoped(monkeypatch):
    monkeypatch.setenv("KEMET_OAUTH_ENCRYPTION_KEY", Fernet.generate_key().decode())
    app = create_app()
    with app.app_context():
        result = SallaWhatsAppProductService.connect_credentials(
            organization_id=1,
            user_id=1,
            credentials={
                "salla_access_token": "salla-token",
                "salla_webhook_secret": "salla-webhook",
                "whatsapp_access_token": "wa-token",
                "whatsapp_phone_number_id": "123456",
                "whatsapp_app_secret": "wa-app",
            },
        )
        assert result["success"] is True
        assert result["stored_encrypted"] is True
        assert resolve_secret("salla_api", "access_token", organization_id=1) == "salla-token"
        assert resolve_secret("meta_whatsapp_cloud_api", "access_token", organization_id=1) == "wa-token"
        assert resolve_secret("meta_whatsapp_cloud_api", "phone_number_id", organization_id=1) == "123456"
        with pytest.raises(RuntimeError, match="secret_not_configured"):
            resolve_secret("salla_api", "access_token", organization_id=2)


def test_product_configuration_verification_never_returns_secret_values(monkeypatch):
    monkeypatch.setenv("KEMET_OAUTH_ENCRYPTION_KEY", Fernet.generate_key().decode())
    app = create_app()
    with app.app_context():
        SallaWhatsAppProductService.connect_credentials(
            organization_id=1,
            user_id=1,
            credentials={
                "salla_access_token": "salla-secret",
                "salla_webhook_secret": "webhook-secret",
                "whatsapp_access_token": "whatsapp-secret",
                "whatsapp_phone_number_id": "phone-123",
            },
        )
        result = SallaWhatsAppProductService.verify_configuration(organization_id=1)
        assert result["verified"] is True
        serialized = str(result)
        assert "salla-secret" not in serialized
        assert "webhook-secret" not in serialized
        assert "whatsapp-secret" not in serialized


def test_product_order_notification_uses_default_phone_id_and_approval_gate(monkeypatch):
    monkeypatch.setenv("KEMET_OAUTH_ENCRYPTION_KEY", Fernet.generate_key().decode())
    app = create_app()
    with app.app_context():
        SallaWhatsAppProductService.connect_credentials(
            organization_id=1,
            user_id=1,
            credentials={
                "salla_access_token": "salla-token",
                "salla_webhook_secret": "salla-webhook",
                "whatsapp_access_token": "wa-token",
                "whatsapp_phone_number_id": "phone-123",
            },
        )
        from app.services.salla_connector_service import SallaConnectorService
        event = SallaConnectorService.normalize_webhook(
            organization_id=1,
            payload={
                "event": "order.created",
                "data": {
                    "id": f"order-{uuid.uuid4().hex}",
                    "customer": {"phone": "201000000000"},
                },
            },
        )
        planned = SallaWhatsAppProductService.prepare_order_notification(
            organization_id=1,
            event=event,
            phone_number_id=SallaWhatsAppProductService.default_phone_number_id(1),
        )
        assert planned["success"] is True
        assert planned["status"] == "approval_required"
        assert planned["approval_id"]
        assert planned["message"]["recipient"] == "201000000000"
