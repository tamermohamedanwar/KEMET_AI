from app.services.channel_adapter_service import channel_adapter_service


def test_whatsapp_ingest_routes_to_kemet_core():
    result = channel_adapter_service.ingest(
        channel="whatsapp", organization_id=1,
        payload={"message_id": "wa-1", "user_id": "wa-user-1", "text": "عايز أعرف السعر"},
    )
    assert result["success"] is True
    assert result["request"]["channel"] == "whatsapp"
    assert result["request"]["language"] == "ar"
    assert result["route"]["next"] == "kemet_core"
    assert result["governance"]["external_execution"] is False


def test_telegram_ingest_preserves_tenant_boundary():
    result = channel_adapter_service.ingest(
        channel="telegram", organization_id=7,
        payload={"external_message_id": "tg-1", "external_user_id": "tg-user-1", "text": "I need help"},
    )
    assert result["envelope"]["organization_id"] == 7
    assert result["request"]["organization_id"] == 7
    assert result["route"]["organization_id"] == 7


def test_channel_ingest_fails_closed_for_missing_identity():
    try:
        channel_adapter_service.ingest(channel="whatsapp", organization_id=1, payload={"text": "hello"})
    except ValueError as exc:
        assert str(exc) == "external_message_id_required"
    else:
        raise AssertionError("missing external identity must fail closed")


def test_response_is_proposal_only():
    result = channel_adapter_service.response_plan(
        channel="telegram", organization_id=1, content="Your request is ready for review.", requires_approval=True
    )
    assert result["delivery"] == "proposal_only"
    assert result["provider"] == "provider_neutral"
    assert result["governance"]["external_execution"] is False
    assert result["requires_approval"] is True
