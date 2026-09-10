def test_normalize_supports_arabic_and_english_channels():
    from app.services.omnichannel_service import omnichannel_service

    ar = omnichannel_service.normalize("whatsapp", "wa-1", "هاتلي مبيعات الأسبوع", organization_id=7)
    en = omnichannel_service.normalize("telegram", "tg-1", "Show this week's sales", organization_id=7)
    assert ar.language == "ar"
    assert en.language == "en"
    assert ar.organization_id == en.organization_id == 7


def test_route_is_shared_and_fail_safe():
    from app.services.omnichannel_service import omnichannel_service

    message = omnichannel_service.normalize("web", "user-1", "Hello")
    result = omnichannel_service.route(message)
    assert result["next"] == "kemet_core"
    assert result["governance"]["external_execution"] is False
    assert result["governance"]["auto_execute"] is False
    assert result["governance"]["human_approval_required"] is True


def test_unknown_channel_is_rejected():
    from app.services.omnichannel_service import omnichannel_service

    try:
        omnichannel_service.normalize("discord", "u1", "Hello")
        assert False
    except ValueError as exc:
        assert str(exc) == "Unsupported channel"
