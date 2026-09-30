from app.services.commerce_fulfillment_service import commerce_fulfillment_service


def test_fulfillment_plan_is_approval_gated():
    result = commerce_fulfillment_service.build_plan(
        organization_id=1,
        business_reference="KEMET-ORDER-001",
        customer={"firstName": "Test", "mobile": "01000000000"},
        shipping_address={"city": "Cairo"},
        cod=1500,
        items=[{"name": "Leather wallet", "quantity": 2}],
    )
    assert result["status"] == "approval_required"
    assert result["order"]["business_reference"] == "KEMET-ORDER-001"
    assert result["order"]["order_key"]
    assert result["fulfillment"]["operation"] == "create_delivery"
    assert result["governance"]["external_execution"] is False


def test_fulfillment_plan_rejects_missing_reference():
    try:
        commerce_fulfillment_service.build_plan(
            organization_id=1,
            business_reference="",
            customer={"firstName": "Test", "mobile": "01000000000"},
            shipping_address={"city": "Cairo"},
            cod=0,
            items=[{"name": "Item", "quantity": 1}],
        )
    except ValueError as exc:
        assert str(exc) == "business_reference_required"
    else:
        raise AssertionError("missing reference must fail closed")
