from app.services.mendes.mendes_governed_pilot_service import mendes_governed_pilot_service


def test_governed_pilot_assembles_full_episode_chain():
    result = mendes_governed_pilot_service.assemble(1)
    assert result["success"] is True
    assert result["status"] == "HUMAN_APPROVAL_REQUIRED"
    assert result["workflow"] == [
        "story_bible", "continuity", "script", "production_backlot",
        "quality_rights_policy", "distribution_package", "measurement", "human_approval",
    ]
    assert result["package"]["series"] == "Hikayat Mendes"
    assert result["package"]["episode"]["episode_id"] == "s1e1"
    assert result["production_job"]["state"] == "PLANNED"


def test_governed_pilot_is_blocked_at_human_approval_boundary():
    result = mendes_governed_pilot_service.assemble(1)
    assert result["publication"]["ready"] is False
    assert result["publication"]["error"] == "publication_approval_required"
    assert result["readiness"]["approval"]["status"] == "pending"
    assert result["readiness"]["approval"]["publication"] == "NOT_REQUESTED"


def test_governed_pilot_has_no_execution_authority_or_mcp():
    result = mendes_governed_pilot_service.assemble(1)
    governance = result["governance"]
    assert governance["external_execution"] is False
    assert governance["auto_publish"] is False
    assert governance["execution_authority"] is False
    assert governance["canonical_runtime_only"] is True
    assert governance["credentials_exposed"] is False
    assert governance["mcp"] is False


def test_governed_pilot_rejects_invalid_tenant():
    try:
        mendes_governed_pilot_service.assemble(0)
    except ValueError as exc:
        assert str(exc) == "organization_required"
    else:
        raise AssertionError("invalid organization accepted")
