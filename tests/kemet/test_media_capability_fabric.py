from app.core.media.capability_fabric import media_capability_fabric
from app.core.media.capabilities import MEDIA_CAPABILITIES
import pytest

def test_snapshot_is_media_scoped_and_non_executing():
    s=media_capability_fabric.snapshot(configured_only=False)
    assert s["execution_authority"] is False
    assert s["mcp"] is False
    assert all(x["capability"] in MEDIA_CAPABILITIES for x in s["capabilities"])
    assert s["fingerprint"]
    assert set(s["failure_classes"]) >= {"timeout", "unavailable", "auth"}

def test_snapshot_exposes_provider_operational_metadata_without_credentials():
    s=media_capability_fabric.snapshot(configured_only=False)
    for item in s["providers"]:
        assert "provider_id" in item
        assert "latency_ms" in item
        assert "cost_status" in item
        assert "failure_class" in item
        assert "api_key" not in item
        assert "secret" not in item

def test_route_rejects_unknown_media_capability():
    with pytest.raises(ValueError, match="unsupported_media_capability"):
        media_capability_fabric.route(["NOT_A_MEDIA_CAPABILITY"], verified=set())

def test_route_requires_capability():
    with pytest.raises(ValueError, match="media_capability_required"):
        media_capability_fabric.route([], verified=set())

def test_route_carries_operational_metadata_without_granting_authority():
    result=media_capability_fabric.route(["TEXT_TO_SPEECH"], verified=set())
    assert result["execution_authority"] is False
    assert result["mcp"] is False
    assert result["provider_metadata"] == []

def test_local_snapshot_reports_truthful_runtime_capabilities():
    snapshot=media_capability_fabric.local_snapshot()
    by_capability={item["capability"]: item for item in snapshot}
    assert by_capability["VIDEO_GENERATION"]["status"] == "HARDWARE_LIMITED"
    assert by_capability["PROCEDURAL_VIDEO_GENERATION"]["status"] == "LOCAL_READY"
    assert by_capability["IMAGE_GENERATION"]["status"] == "NOT_IMPLEMENTED"
    assert all(item["external_provider_required"] is False for item in snapshot)
    assert all(item["execution_authority"] is False for item in snapshot)

def test_local_only_mode_never_routes_to_external_provider():
    result=media_capability_fabric.route(["PROCEDURAL_VIDEO_GENERATION"], verified=set(), local_only=True)
    assert result["local_only_mode"] is True
    assert result["provider_metadata"] == []
    assert result["success"] is True
    assert all(item["provider_id"] == "kemet_local" for item in result["candidates"])

def test_local_only_mode_blocks_hardware_limited_generation_truthfully():
    result=media_capability_fabric.route(["VIDEO_GENERATION"], verified=set(), local_only=True)
    assert result["success"] is False
    assert result["error"] == "local_capability_unavailable"
    assert result["unavailable_capabilities"] == ["VIDEO_GENERATION"]

def test_local_only_mode_blocks_unimplemented_capability_truthfully():
    result=media_capability_fabric.route(["IMAGE_GENERATION"], verified=set(), local_only=True)
    assert result["success"] is False
    assert result["error"] == "local_capability_unavailable"
    assert result["unavailable_capabilities"] == ["IMAGE_GENERATION"]


def test_canonical_truth_distinguishes_local_ready_hardware_and_unimplemented():
    assert media_capability_fabric.resolve_truth("TEXT_TO_SPEECH")["state"] == "BLOCKED"
    assert media_capability_fabric.resolve_truth("VIDEO_GENERATION")["state"] == "HARDWARE_LIMITED"
    assert media_capability_fabric.resolve_truth("IMAGE_GENERATION")["state"] == "NOT_IMPLEMENTED"


def test_provider_configuration_does_not_create_self_owned_ready_state():
    assert media_capability_fabric.resolve_truth("VIDEO_GENERATION")["evidence_status"] != "VERIFIED_PROVIDER"
    assert media_capability_fabric.resolve_truth("VIDEO_GENERATION")["provider_independent"] is True
