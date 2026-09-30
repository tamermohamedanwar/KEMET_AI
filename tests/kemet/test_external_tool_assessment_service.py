from app.services.external_tool_assessment_service import external_tool_assessment_service


def test_read_only_discovery_can_be_assessed_when_license_is_verified():
    result = external_tool_assessment_service.assess(
        tool_id="sender-pro",
        provenance="vendor",
        source_uri="https://senderprov.com",
        license_status="vendor_terms_reviewed",
        requested_capabilities=("discovery", "lead_evidence"),
    )
    assert result.assessment_status == "approved_read_only"
    assert result.allowed_capabilities == ("discovery", "lead_evidence")
    assert result.external_side_effects is False


def test_unknown_license_fails_closed():
    result = external_tool_assessment_service.assess(
        tool_id="unknown-tool", provenance="external", source_uri=None,
        license_status="unknown", requested_capabilities=("discovery",),
    )
    assert result.assessment_status == "review_required"
    assert result.blocked_capabilities == ("discovery",)


def test_credentials_or_side_effects_force_review():
    result = external_tool_assessment_service.assess(
        tool_id="sender-pro", provenance="vendor", source_uri="https://senderprov.com",
        license_status="verified", credential_access=True,
        external_side_effects=True, requested_capabilities=("discovery",),
    )
    assert result.assessment_status == "review_required"


def test_assessment_digest_is_deterministic():
    kwargs = dict(tool_id="sender-pro", provenance="vendor", source_uri="https://senderprov.com",
                  license_status="verified", permissions=("storage", "tabs"),
                  host_access=("https://example.com/*",), requested_capabilities=("discovery",))
    assert external_tool_assessment_service.assess(**kwargs).digest == external_tool_assessment_service.assess(**kwargs).digest
