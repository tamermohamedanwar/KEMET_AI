import pytest

from app.core.integration.channel_adapter import get_channel_adapter


def test_channel_adapter_normalizes_without_external_execution():
    adapter = get_channel_adapter("whatsapp")
    message = adapter.inbound(
        text="مرحبا",
        external_message_id="wa-1",
        organization_id=9,
    )
    plan = adapter.response_plan(message, content="أهلاً بك")
    assert message.channel == "whatsapp"
    assert message.language == "ar"
    assert plan["executed"] is False
    assert plan["governance"]["external_execution"] is False
    assert plan["governance"]["auto_execute"] is False


def test_channel_adapter_rejects_unknown_channel():
    with pytest.raises(ValueError):
        get_channel_adapter("signal")
