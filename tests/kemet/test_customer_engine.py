from app.core.customer import CustomerEngine


def test_customer_context():
    result = CustomerEngine.build_customer_context(
        customer_id=101,
        channel="whatsapp",
        message="I need help with my order.",
    )

    assert result["success"] is True
    assert result["engine"] == "kemet_customer"
    assert result["customer"]["id"] == "101"


def test_supported_channel_routing():
    context = CustomerEngine.build_customer_context(
        customer_id=101,
        channel="whatsapp",
        message="Hello",
    )

    result = CustomerEngine.route_message(context)

    assert result["success"] is True
    assert result["engine"] == "kemet_omnichannel"
    assert result["channel"] == "whatsapp"
    assert result["requires_approval"] is True


def test_external_execution_is_blocked():
    context = CustomerEngine.build_customer_context(
        customer_id=101,
        channel="email",
        message="Please contact me.",
    )

    result = CustomerEngine.route_message(context)

    assert result["external_execution"] is False
