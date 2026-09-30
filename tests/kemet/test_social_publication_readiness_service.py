from app.services.social_publication_readiness_service import social_publication_readiness_service


def test_youtube_blocks_before_audit_or_human_approval():
    result = social_publication_readiness_service.evaluate(
        organization_id=1, platform="youtube",
        metadata={"title": "x", "description": "y", "audience": "not_made_for_kids"},
        connected=True, publishing_authorized=True, api_audited=False, human_approval=False,
    )
    assert result["ready"] is False
    assert result["error"] == "platform_api_audit_required"
    assert result["execution_authority"] is False


def test_tiktok_requires_audit_and_aigc_metadata():
    result = social_publication_readiness_service.evaluate(
        organization_id=1, platform="tiktok",
        metadata={"title": "x", "privacy_level": "PUBLIC_TO_EVERYONE", "is_aigc": True},
        connected=True, publishing_authorized=True, api_audited=False, human_approval=True,
    )
    assert result["error"] == "platform_api_audit_required"


def test_ready_state_requires_human_approval_and_preserves_digest():
    result = social_publication_readiness_service.evaluate(
        organization_id=1, platform="instagram", metadata={"caption": "x"},
        connected=True, publishing_authorized=True, human_approval=True,
    )
    assert result["ready"] is True
    assert result["status"] == "READY_FOR_CANONICAL_EXECUTION"
    assert len(result["evidence_digest"]) == 64
    assert result["execution_authority"] is False


def test_missing_metadata_fails_closed():
    result = social_publication_readiness_service.evaluate(
        organization_id=1, platform="facebook", metadata={},
        connected=True, publishing_authorized=True, human_approval=True,
    )
    assert result["error"] == "metadata_required"
    assert result["ready"] is False
