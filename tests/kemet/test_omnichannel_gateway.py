import pytest
from app.services.omnichannel_gateway import omnichannel_gateway


def test_normalize_arabic_web_message():
    message = omnichannel_gateway.normalize(channel="web", text="هاتلي مبيعات الأسبوع", external_message_id="w1", user_id=7, organization_id=3, conversation_id=11)
    assert message.channel == "web" and message.language == "ar" and message.organization_id == 3
    routed = omnichannel_gateway.route(message)
    canonical = omnichannel_gateway.canonical_request(message)
    assert routed["next"] == "kemet_core" and canonical["request_id"] == message.message_id


def test_normalize_english_telegram_message():
    message = omnichannel_gateway.normalize(channel="telegram", text="Show this week's sales", external_message_id="t1")
    assert message.channel == "telegram" and message.language == "en"


def test_whatsapp_is_supported_without_network_execution():
    message = omnichannel_gateway.normalize(channel="whatsapp", text="Hello", external_message_id="wa1")
    envelope = omnichannel_gateway.response_envelope(message, content="Ready")
    assert envelope["channel"] == "whatsapp" and envelope["executed"] is False
    assert envelope["governance"]["external_execution"] is False


def test_invalid_channel_and_empty_text_fail_closed():
    with pytest.raises(ValueError):
        omnichannel_gateway.normalize(channel="email", text="Hello")
    with pytest.raises(ValueError):
        omnichannel_gateway.normalize(channel="web", text=" ")


def test_approval_is_explicit_in_response_envelope():
    message = omnichannel_gateway.normalize(channel="web", text="Request refund")
    envelope = omnichannel_gateway.response_envelope(message, content="Approval required", requires_approval=True)
    assert envelope["requires_approval"] is True and envelope["executed"] is False
    assert envelope["governance"]["human_approval_required"] is True


def test_route_preserves_tenant_and_identity():
    message = omnichannel_gateway.normalize(channel="whatsapp", text="Need help", external_message_id="wa2", user_id=9, organization_id=4, conversation_id=21)
    routed = omnichannel_gateway.route(message)
    assert routed["user_id"] == 9 and routed["organization_id"] == 4
    assert routed["conversation_id"] == 21 and routed["external_execution"] is False


def test_gateway_health_is_fail_closed():
    health = omnichannel_gateway.health()
    assert health["status"] == "ok"
    assert health["channels"] == ["web", "whatsapp", "telegram"]
    assert health["governance"]["external_execution"] is False
