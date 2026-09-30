from app.services.cinematic_quality_readiness_gate import cinematic_quality_readiness_gate


def _evidence(value=True):
    return {key: {"verified": value} for key in cinematic_quality_readiness_gate.REQUIRED}


def test_cinematic_quality_gate_requires_all_dimensions():
    result = cinematic_quality_readiness_gate.evaluate(organization_id=7, project_id="film-1", evidence=_evidence())
    assert result["production_ready"] is True
    assert result["status"] == "READY"
    assert result["quality_contract"]["canonical_references_required"] is True
    assert result["mcp"] is False


def test_cinematic_quality_gate_fails_closed():
    evidence = _evidence()
    evidence["animation_motion"] = {"verified": False}
    result = cinematic_quality_readiness_gate.evaluate(organization_id=7, project_id="film-1", evidence=evidence)
    assert result["production_ready"] is False
    assert result["status"] == "BLOCKED"
