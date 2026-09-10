def test_saas_control_plane_fails_closed_without_org():
    from app.services.saas_control_plane import saas_control_plane
    result = saas_control_plane.overview(None)
    assert result["success"] is False
    assert result["error"] == "organization_required"


def test_saas_control_plane_capability_requires_org():
    from app.services.saas_control_plane import saas_control_plane
    result = saas_control_plane.check_capability(None, "kemet.business_insights")
    assert result["allowed"] is False
    assert result["reason"] == "organization_required"


def test_saas_control_plane_has_no_execution_policy():
    from app.services.saas_control_plane import saas_control_plane
    assert saas_control_plane.VERSION == "1.0"
    assert saas_control_plane.CAPABILITY_FEATURES["kemet.business_insights"] == "bos"
