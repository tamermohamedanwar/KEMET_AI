from app.services.content_social_governance_service import content_social_governance_service


def _asset(state="APPROVED", version=1):
    return content_social_governance_service.build_asset(
        organization_id=1,
        content_id="content-1",
        version=version,
        content_type="short",
        language="ar-EG",
        payload={"title": "Test", "body": "Original content"},
        lifecycle_state=state,
    )


def test_asset_version_and_digest_are_bound():
    asset = _asset()
    assert asset["schema"] == "kemet.content_asset.v1"
    assert asset["version"] == 1
    assert asset["canonical_digest"]


def test_approval_is_bound_to_exact_content_version_and_digest():
    asset = _asset()
    approval = content_social_governance_service.create_approval(asset=asset, approver_id="7")
    assert content_social_governance_service.validate_approval_for_publish(asset=asset, approval=approval)["valid"] is True
    changed = dict(asset, version=2)
    assert content_social_governance_service.validate_approval_for_publish(asset=changed, approval=approval)["valid"] is False


def test_publish_intent_requires_approved_content():
    asset = _asset("DRAFT")
    try:
        content_social_governance_service.create_publishing_intent(
            asset=asset, platform="instagram", account_ref="ig-1", idempotency_key="idem-1"
        )
    except ValueError as exc:
        assert str(exc) == "approved_content_required"
    else:
        raise AssertionError("unapproved content created publishing intent")


def test_publish_intent_is_tenant_and_idempotency_bound():
    asset = _asset()
    intent = content_social_governance_service.create_publishing_intent(
        asset=asset, platform="linkedin", account_ref="li-1", idempotency_key="idem-1"
    )
    assert intent["organization_id"] == 1
    assert intent["content_version"] == 1
    assert intent["idempotency_key"] == "idem-1"
    assert intent["risk_tier"] == "high"


def test_connector_state_does_not_claim_ready_from_configuration_only():
    assert content_social_governance_service.connector_state(configured=True, authenticated=False, verified=False) == "CONFIGURED"
    assert content_social_governance_service.connector_state(configured=True, authenticated=True, verified=False) == "AUTHENTICATED"
    assert content_social_governance_service.connector_state(configured=True, authenticated=True, verified=True) == "READY"
    assert content_social_governance_service.connector_state(configured=True, authenticated=True, verified=True, healthy=False) == "DEGRADED"


def test_asset_validation_rejects_cross_tenant_and_unsupported_claims():
    asset = _asset()
    asset.update({
        "objective": "awareness",
        "audience": "business owners",
        "topic": "governance",
        "key_message": "approval before action",
        "hook": "Control first",
        "body": "Review evidence before external execution.",
        "target_platforms": ["instagram"],
        "claims": [{"claim": "unsupported", "evidence_state": "unsupported"}],
    })
    result = content_social_governance_service.validate_asset(asset=asset, tenant_id=2)
    assert result["valid"] is False
    assert "tenant_mismatch" in result["errors"]
    assert "unsupported_claim" in result["errors"]


def test_asset_validation_accepts_supported_claim_and_canonical_payload():
    payload = {
        "objective": "education",
        "audience": "business owners",
        "topic": "governance",
        "key_message": "approval before action",
        "hook": "Control first",
        "body": "Review evidence before external execution.",
        "target_platforms": ["instagram"],
        "claims": [{"claim": "approval is required", "evidence_state": "supported", "evidence_ref": "governance"}],
    }
    asset = content_social_governance_service.build_asset(
        organization_id=1, content_id="validated-1", version=1,
        content_type="educational", language="ar-EG", payload=payload,
        lifecycle_state="READY_FOR_REVIEW",
    )
    asset.update(payload)
    result = content_social_governance_service.validate_asset(asset=asset, tenant_id=1)
    assert result["valid"] is True
