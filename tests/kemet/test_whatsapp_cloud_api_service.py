import pytest

from app.services.whatsapp_cloud_api_service import whatsapp_cloud_api_service


def test_contract_is_high_risk_and_human_approved():
    contract = whatsapp_cloud_api_service.contract(organization_id=7)
    assert contract.connector_id == "whatsapp_cloud_api"
    assert contract.risk_tier == "high"
    assert contract.approval_level == "human"
    assert contract.validate()["valid"] is True


def test_send_plan_has_no_secret_and_is_not_executed(monkeypatch):
    monkeypatch.setattr(
        "app.core.egress_policy.socket.getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("157.240.241.17", 0))],
    )
    monkeypatch.setenv("KEMET_META_GRAPH_VERSION", "v23.0")
    monkeypatch.setenv("KEMET_META_ACCESS_TOKEN", "do-not-leak")
    plan = whatsapp_cloud_api_service.plan_send_text(
        organization_id=7,
        recipient="201000000000",
        content="Order received.",
        external_message_id="inbound-1",
        phone_number_id="123456",
    )
    assert plan["delivery"] == "approval_required"
    assert plan["governance"]["external_execution"] is False
    assert plan["governance"]["human_approval_required"] is True
    assert "do-not-leak" not in str(plan)
    assert plan["endpoint"].endswith("/v23.0/123456/messages")
    assert plan["payload"]["to"] == "201000000000"


def test_send_plan_requires_identity_and_content():
    with pytest.raises(ValueError, match="recipient_required"):
        whatsapp_cloud_api_service.plan_send_text(
            organization_id=7,
            recipient="",
            content="hello",
            external_message_id="inbound-1",
        )
    with pytest.raises(ValueError, match="message_content_required"):
        whatsapp_cloud_api_service.plan_send_text(
            organization_id=7,
            recipient="201000000000",
            content="",
            external_message_id="inbound-1",
        )


def test_template_plan_is_approval_gated_and_deterministic():
    plan = whatsapp_cloud_api_service.plan_send_template(
        organization_id=7,
        recipient="201000000000",
        template_name="order_update",
        language_code="ar",
        external_message_id="inbound-2",
        phone_number_id="123456",
        parameters=["ORD-1", "Bosta"],
    )
    assert plan["operation"] == "send_template"
    assert plan["delivery"] == "approval_required"
    assert plan["governance"]["canonical_executor"] == "kemet"
    assert plan["payload"]["template"]["name"] == "order_update"
    assert len(plan["idempotency_key"]) == 64


def test_delivery_event_is_inbound_only():
    result = whatsapp_cloud_api_service.delivery_event(
        organization_id=7,
        payload={"message_id": "wamid.1", "status": "delivered"},
    )
    assert result["status"] == "delivered"
    assert result["durable_ingress_required"] is True
    assert result["governance"]["external_execution"] is False


def test_delivery_event_rejects_unknown_status():
    with pytest.raises(ValueError, match="invalid_delivery_status"):
        whatsapp_cloud_api_service.delivery_event(
            organization_id=7,
            payload={"message_id": "wamid.1", "status": "queued"},
        )


def test_template_plan_rejects_missing_template():
    with pytest.raises(ValueError, match="template_name_required"):
        whatsapp_cloud_api_service.plan_send_template(
            organization_id=7,
            recipient="201000000000",
            template_name="",
            language_code="ar",
            external_message_id="inbound-3",
        )
