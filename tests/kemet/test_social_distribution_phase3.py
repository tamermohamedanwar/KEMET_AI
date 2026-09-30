from app.services.social_distribution_phase3_service import social_distribution_phase3_service
from app.services.social_measurement_phase3_service import social_measurement_phase3_service


def test_distribution_snapshot_is_fail_closed():
    snapshot = social_distribution_phase3_service.snapshot(1)
    assert snapshot["schema"] == "kemet.social_distribution_phase3.v1"
    assert all(item["approval_required"] for item in snapshot["channels"])
    assert all(not item["execution_authority"] for item in snapshot["channels"])


def test_distribution_plan_requires_approval_and_has_no_side_effect():
    result = social_distribution_phase3_service.plan(
        1, {"content_id": "mendes-s1e1", "asset_digest": "abc"}, ["youtube", "tiktok"]
    )
    assert result["approval"]["state"] == "PENDING"
    assert result["executed"] is False
    assert result["external_side_effect"] is False
    assert result["content_digest"]


def test_distribution_rejects_unknown_channels():
    try:
        social_distribution_phase3_service.plan(1, {"x": 1}, ["unknown"])
    except ValueError as exc:
        assert str(exc) == "unsupported_channel"
    else:
        raise AssertionError("unsupported channel accepted")


def test_measurement_preserves_unknown_revenue_as_null():
    result = social_measurement_phase3_service.normalize(1, "youtube", {"views": 10})
    assert result["metrics"]["views"] == 10.0
    assert result["metrics"]["revenue"] is None
    assert result["revenue_is_authoritative"] is False
    assert result["synthetic"] is False


def test_measurement_is_evidence_bound():
    result = social_measurement_phase3_service.normalize(
        1, "facebook", {"views": 100, "qualified_views": 80, "revenue": 1.25}
    )
    assert result["evidence_digest"]
    assert result["revenue_is_authoritative"] is True


def test_measurement_rejects_missing_channel():
    try:
        social_measurement_phase3_service.normalize(1, "", {})
    except ValueError as exc:
        assert str(exc) == "channel_required"
    else:
        raise AssertionError("missing channel accepted")


def test_measurement_keeps_revenue_null_when_unavailable():
    result = social_measurement_phase3_service.normalize(1, "tiktok", {"views": 5})
    assert result["metrics"]["revenue"] is None
    assert result["revenue_is_authoritative"] is False


def test_snapshot_contains_all_governed_channels():
    channels = {item["channel"] for item in social_distribution_phase3_service.snapshot(1)["channels"]}
    assert channels == {"youtube", "facebook", "instagram", "tiktok"}


def test_measurement_marks_real_numeric_revenue_as_authoritative():
    result = social_measurement_phase3_service.normalize(1, "youtube", {"revenue": 2.5})
    assert result["metrics"]["revenue"] == 2.5
    assert result["revenue_is_authoritative"] is True


def test_distribution_digest_changes_with_content():
    first = social_distribution_phase3_service.plan(1, {"content_id": "a"}, ["youtube"])
    second = social_distribution_phase3_service.plan(1, {"content_id": "b"}, ["youtube"])
    assert first["content_digest"] != second["content_digest"]


def test_distribution_is_explicitly_non_mcp():
    snapshot = social_distribution_phase3_service.snapshot(1)
    assert snapshot["governance"]["mcp"] is False


def test_measurement_ignores_boolean_as_numeric_metric():
    result = social_measurement_phase3_service.normalize(1, "youtube", {"views": True})
    assert result["metrics"]["views"] is None


def test_measurement_is_tenant_bound():
    result = social_measurement_phase3_service.normalize(7, "facebook", {"views": 1})
    assert result["organization_id"] == 7


def test_plan_is_not_publish_request():
    result = social_distribution_phase3_service.plan(1, {"content_id": "x"}, ["youtube"])
    assert result["approval"]["required"] is True
    assert result["executed"] is False


def test_governance_disables_auto_publish():
    governance = social_distribution_phase3_service.snapshot(1)["governance"]
    assert governance["auto_publish"] is False
    assert governance["human_approval_required"] is True


def test_snapshot_is_tenant_specific():
    assert social_distribution_phase3_service.snapshot(3)["organization_id"] == 3


def test_plan_rejects_empty_content_package():
    try:
        social_distribution_phase3_service.plan(1, {}, ["youtube"])
    except ValueError as exc:
        assert str(exc) == "content_package_required"
    else:
        raise AssertionError("empty content package accepted")
