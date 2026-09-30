from app.services.mendes.mendes_media_binding_service import mendes_media_binding_service
from app.services.mendes.mendes_pilot_episode_service import mendes_pilot_episode_service


def test_mendes_pilot_binds_canonical_media_contracts():
    result = mendes_pilot_episode_service.build(organization_id=1)
    package = result["package"]
    binding = package["media_binding"]
    assert binding["status"] == "media_contracts_bound"
    assert set(binding["contracts"]) == {"content_intent", "content_blueprint", "scene_plan", "asset_plan", "voice_plan", "render_plan"}
    assert binding["binding"]["governance"]["execution_authority"] is False
    assert binding["binding"]["governance"]["external_execution"] is False
    assert binding["binding"]["governance"]["mcp"] is False


def test_mendes_binding_is_deterministic():
    package = mendes_pilot_episode_service.build(organization_id=1)["package"]
    first = mendes_media_binding_service.bind(organization_id=1, episode_package=package)
    second = mendes_media_binding_service.bind(organization_id=1, episode_package=package)
    assert first["binding"]["binding_digest"] == second["binding"]["binding_digest"]
    assert first["binding"]["contract_digests"] == second["binding"]["contract_digests"]


def test_mendes_binding_is_tenant_safe():
    package = mendes_pilot_episode_service.build(organization_id=1)["package"]
    try:
        mendes_media_binding_service.bind(organization_id=2, episode_package=package)
    except ValueError as exc:
        assert str(exc) == "episode_package_tenant_mismatch"
    else:
        raise AssertionError("tenant mismatch must fail closed")


def test_mendes_binding_requires_pending_human_approval():
    package = mendes_pilot_episode_service.build(organization_id=1)["package"]
    package["approval"] = {"required": True, "status": "approved"}
    try:
        mendes_media_binding_service.bind(organization_id=1, episode_package=package)
    except ValueError as exc:
        assert str(exc) == "human_approval_required"
    else:
        raise AssertionError("approved package must not bypass binding gate")
