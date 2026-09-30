import pytest

from app.services.mendes.mendes_adaptation_lineage_service import mendes_adaptation_lineage_service


def _source():
    return mendes_adaptation_lineage_service.create_source(
        organization_id=1, asset_id="mendes-s1e1", version=1,
        digest="a" * 64, media_path="instance/production/mendes/s1e1.mp4",
    )


def test_create_once_source_is_versioned_and_tenant_bound():
    source = _source()
    assert source["schema"] == "kemet.mendes.source_asset.v1"
    assert source["version"] == 1
    assert source["digest"] == "a" * 64


def test_adaptation_preserves_exact_source_lineage():
    source = _source()
    adaptation = mendes_adaptation_lineage_service.create_adaptation(
        source=source, platform="youtube", adaptation_version=1,
        payload={"title": "Hikayat Mendes", "aspect_ratio": "9:16"},
    )
    result = mendes_adaptation_lineage_service.validate_lineage(
        source=source, adaptation=adaptation, organization_id=1,
    )
    assert result["valid"] is True
    assert adaptation["source_digest"] == source["digest"]
    assert adaptation["publication_status"] == "NOT_REQUESTED"


def test_lineage_rejects_cross_tenant_and_source_version_swap():
    source = _source()
    adaptation = mendes_adaptation_lineage_service.create_adaptation(
        source=source, platform="tiktok", adaptation_version=1,
        payload={"duration": 90},
    )
    changed = dict(adaptation, organization_id=2, source_version=2)
    result = mendes_adaptation_lineage_service.validate_lineage(
        source=source, adaptation=changed, organization_id=1,
    )
    assert result["valid"] is False
    assert result["checks"]["tenant"] is False
    assert result["checks"]["source_version"] is False


def test_unsupported_platform_is_fail_closed():
    with pytest.raises(ValueError, match="unsupported_platform"):
        mendes_adaptation_lineage_service.create_adaptation(
            source=_source(), platform="unknown", adaptation_version=1, payload={},
        )
