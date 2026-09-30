from app.services.content_factory_service import content_factory_service


def base_payload():
    return dict(
        organization_id=1,
        title="The Hidden Door of Mendes",
        premise="A young resident discovers a sealed chamber and must decide whether to open it.",
        audience="Arabic-speaking family audience",
        content_type="story",
        language="ar-EG",
        platforms=["youtube", "facebook", "instagram", "tiktok"],
        duration_seconds=90,
        rights_status="original",
        era_label="Ancient Mendes",
        era_type="inspired",
        season_number=1,
        episode_number=1,
        characters=[{"character_id": "hor", "name": "Hor", "role": "young resident"}],
        cliffhanger="The seal moves.",
    )


def test_factory_builds_complete_governed_package():
    result = content_factory_service.build(**base_payload())
    assert result["schema"] == "kemet.content_factory.v1"
    assert result["status"] == "review_required"
    assert result["package_digest"]
    assert result["content"]["episode_id"] == "s1e1"
    assert result["production"]["quality_gates"]["rights"] == "required"
    assert result["distribution"]["approval"]["required"] is True
    assert result["approval"]["decision"] == "PENDING"
    assert result["governance"]["execution_authority"] is False
    assert result["governance"]["auto_publish"] is False


def test_pending_rights_blocks_quality_and_approval():
    payload = base_payload()
    payload["rights_status"] = "pending_review"
    result = content_factory_service.build(**payload)
    assert result["quality_gate"]["status"] == "BLOCKED"
    assert "rights" in result["quality_gate"]["blocked_by"]
    assert result["approval"]["decision"] == "PENDING"


def test_original_content_can_proceed_without_source_ids():
    payload = base_payload()
    payload["source_ids"] = []
    result = content_factory_service.build(**payload)
    checks = {item["name"]: item["passed"] for item in result["quality_gate"]["checks"]}
    assert checks["provenance"] is True


def test_invalid_platform_fails_closed():
    payload = base_payload()
    payload["platforms"] = ["unknown_platform"]
    try:
        content_factory_service.build(**payload)
    except ValueError as exc:
        assert str(exc) == "unsupported_platform"
    else:
        raise AssertionError("unsupported platform was accepted")


def test_package_digest_is_deterministic():
    first = content_factory_service.build(**base_payload())
    second = content_factory_service.build(**base_payload())
    assert first["package_digest"] == second["package_digest"]


def test_multilingual_production_profile_is_canonical_state():
    payload = base_payload()
    payload.update(dialect="sa", production_profile="cinematic", language="ar-EG")
    result = content_factory_service.build(**payload)
    assert result["content"]["dialect"] == "sa"
    assert result["content"]["production_profile"] == "cinematic"
    assert result["governance"]["execution_authority"] is False


def test_unsupported_dialect_fails_closed():
    payload = base_payload()
    payload["dialect"] = "unknown"
    try:
        content_factory_service.build(**payload)
    except ValueError as exc:
        assert str(exc) == "unsupported_dialect"
    else:
        raise AssertionError("unsupported dialect was accepted")


def test_production_plan_exposes_canonical_capability_truth_and_free_compute_gate():
    result = content_factory_service.build(**base_payload())
    plan = result["production_plan"]
    assert plan["schema"] == "kemet.production_plan.v1"
    assert plan["production_profile"]["profile_id"] == "story_narrative"
    assert plan["approval_required"] is True
    assert plan["external_execution"] is False
    assert any(item["kind"] == "voice" for item in plan["capabilities"])
    assert any(item["kind"] == "video" and item["state"] == "HARDWARE_LIMITED" for item in plan["capabilities"])
    assert any(item["kind"] == "image" and item["state"] == "NOT_IMPLEMENTED" for item in plan["capabilities"])
    assert plan["digest"]


def test_idea_contract_does_not_fabricate_market_signals():
    result = content_factory_service.build(**base_payload())
    signals = result["idea"]["signals"]
    assert signals["demand_score"] is None
    assert signals["competition_score"] is None
    assert signals["monetization_score"] is None
    assert signals["confidence"] == "unmeasured"
