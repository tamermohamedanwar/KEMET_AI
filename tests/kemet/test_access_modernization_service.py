from app.services.access_modernization_service import access_modernization_service


def test_access_assessment_covers_full_legacy_surface():
    result = access_modernization_service.assess(
        organization_id=1,
        source_format="accdb",
        source_identity="company.accdb",
        observed_objects=("tables", "relationships", "queries", "forms", "reports", "vba"),
    )
    assert result.status == "assessment_ready"
    assert result.human_review_required is True
    assert "vba" in result.objects
    assert "backend_business_logic" in {row["web_equivalent"] for row in result.migration_matrix}


def test_access_assessment_fails_closed_on_invalid_source():
    for kwargs in (
        dict(organization_id=0, source_format="accdb", source_identity="x.accdb"),
        dict(organization_id=1, source_format="xlsx", source_identity="x.xlsx"),
        dict(organization_id=1, source_format="accdb", source_identity=""),
    ):
        try:
            access_modernization_service.assess(**kwargs)
            assert False
        except ValueError:
            pass


def test_access_assessment_digest_is_deterministic():
    kwargs = dict(
        organization_id=2,
        source_format="mdb",
        source_identity="legacy.mdb",
        observed_objects=("queries", "tables", "forms"),
    )
    first = access_modernization_service.assess(**kwargs)
    second = access_modernization_service.assess(**kwargs)
    assert first.digest == second.digest


def test_access_vba_and_macros_raise_explicit_review_risk():
    result = access_modernization_service.assess(
        organization_id=1,
        source_format="accdb",
        source_identity="legacy.accdb",
        observed_objects=("macros", "vba"),
    )
    assert "executable_logic_requires_manual_review" in result.risks
