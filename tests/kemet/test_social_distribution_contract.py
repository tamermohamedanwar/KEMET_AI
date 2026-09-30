from app.services.social_distribution_contract import SocialDistributionContract


def test_social_distribution_is_provider_neutral_and_approval_gated():
    plan = SocialDistributionContract.plan(
        "youtube", asset_uri="asset://video-1", title="Demo", caption="Test"
    )
    assert plan["platform"] == "youtube"
    assert plan["approval_required"] is True
    assert plan["execution_authority"] is False
    assert plan["governed_executor"] == "kemet_canonical_runtime"
    assert plan["provider_credentials"] == "secret_boundary_only"


def test_platform_capabilities_are_explicit():
    telegram = SocialDistributionContract.plan("telegram", asset_uri="asset://v")
    whatsapp = SocialDistributionContract.plan("whatsapp", asset_uri="asset://v")
    assert "video" in telegram["capabilities"]
    assert "template_message" in whatsapp["capabilities"]
    assert telegram["status"] == "proposal_only"


def test_unknown_platform_fails_closed():
    try:
        SocialDistributionContract.plan("unknown", asset_uri="asset://v")
    except ValueError as exc:
        assert str(exc) == "unsupported_platform"
    else:
        raise AssertionError("unsupported platform must fail closed")
