import pytest

from app.services.ecommerce_creative_service import ecommerce_creative_service


def test_builds_provider_neutral_commerce_brief():
    result = ecommerce_creative_service.build_brief(
        {"name": "Kemet CRM", "features": ["lead scoring", "follow-up"]},
        objective="sales",
        audience="small businesses",
        channel="instagram",
        output_type="model_image",
    )
    assert result["success"] is True
    assert result["brief"]["product_name"] == "Kemet CRM"
    assert result["brief"]["channel"] == "instagram"
    assert result["brief"]["output_type"] == "model_image"
    assert "preserve_product_identity" in result["brief"]["constraints"]
    assert result["governance"]["read_only"] is True
    assert result["governance"]["external_execution"] is False


def test_missing_product_name_fails_closed():
    with pytest.raises(ValueError, match="product_name_required"):
        ecommerce_creative_service.build_brief({})


def test_unsupported_output_type_fails_closed():
    with pytest.raises(ValueError, match="unsupported_output_type"):
        ecommerce_creative_service.build_brief(
            {"name": "Product"}, output_type="autonomous_ad_campaign"
        )


def test_creative_brief_never_claims_revenue_or_causal_attribution():
    result = ecommerce_creative_service.build_brief({"name": "Product"})
    assert result["commercial"]["revenue"] == "not_available"
    assert result["commercial"]["roi"] == "not_proven"
    assert result["commercial"]["causal_claim"] is False
    assert "publish_without_approval" in result["prompt_contract"]["must_not"]
