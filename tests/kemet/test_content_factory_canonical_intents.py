from app.services.content_factory_service import content_factory_service


def payload(intent):
    return dict(
        organization_id=1,
        title=f"{intent} factory contract",
        premise="A canonical production request for contract verification.",
        audience="Arabic-speaking audience",
        content_type=intent,
        language="ar-EG",
        dialect="eg",
        production_profile="auto",
        platforms=["youtube"],
        duration_seconds=60,
        rights_status="original",
    )


def test_content_intent_resolves_to_existing_profile_and_spec():
    result = content_factory_service.build(**payload("educational"))
    plan = result["production_plan"]
    assert plan["content_intent"] == "educational"
    assert plan["production_profile"]["profile_id"] == "educational"
    assert plan["production_spec"]["schema"] == "kemet.content_intent.v1"
    assert plan["production_spec"]["contract_type"] == "kemet.content_intent.v1"
    assert plan["capability_requirements"]


def test_multiple_modalities_share_one_factory_contract():
    for intent in ("image", "audio", "voice", "document", "social_post", "commercial", "cartoon", "motion_graphics"):
        result = content_factory_service.build(**payload(intent))
        assert result["content"]["content_intent"] == intent
        assert result["production_plan"]["production_spec"]["payload"]["content_intent"] == intent
        assert result["production_plan"]["approval_required"] is True
        assert result["governance"]["execution_authority"] is False


def test_capability_requirements_are_derived_from_intent():
    image = content_factory_service.build(**payload("image"))["production_plan"]["capability_requirements"]
    video = content_factory_service.build(**payload("commercial"))["production_plan"]["capability_requirements"]
    image_caps = {item["capability"] for item in image}
    video_caps = {item["capability"] for item in video}
    assert "IMAGE_GENERATION" in image_caps
    assert "VIDEO_GENERATION" in video_caps
    assert "VOICE_SYNTHESIS" in video_caps


def test_provider_identity_is_not_part_of_production_spec():
    result = content_factory_service.build(**payload("image"))
    spec = result["production_plan"]["production_spec"]
    assert "provider_id" not in spec["payload"]
    assert "model" not in spec["payload"]


def test_content_factory_exposes_truthful_routing_decision():
    result = content_factory_service.build(**payload("commercial"))
    decision = result["production_plan"]["routing_decision"]
    assert decision["content_intent"] == "commercial"
    assert decision["status"] in {"HARDWARE_BLOCKED", "NOT_SUPPORTED", "WAIT_FOR_CAPACITY", "PLAN_ONLY", "GOVERNANCE_BLOCKED", "EXECUTE_NOW"}
    assert decision["governance"]["execution_authority"] is False
    assert decision["selection"] is None or decision["selection"].get("execution_path") == "kemet_local"


def test_content_factory_binds_one_canonical_production_graph():
    result = content_factory_service.build(**payload("commercial"))
    plan = result["production_plan"]
    graph = plan["production_graph"]
    assert graph["schema"] == "kemet.cinematic.production_graph.v1"
    assert graph["production_spec_digest"] == plan["production_spec"]["digest"]
    assert graph["source_of_truth"] == "canonical_production_state"
    assert graph["checkpointing"] is True
    assert graph["resumable"] is True
    assert graph["targeted_regeneration"] is True
    assert plan["production_memory"]["canonical"] is True


def test_production_graph_localizes_downstream_impact():
    from app.services.cinematic_production_os import cinematic_production_os
    state = cinematic_production_os.build_state(organization_id=1, project_id="p1", stage="spec")
    spec = {"organization_id": 1, "digest": "s1", "content_intent": "commercial"}
    graph = cinematic_production_os.build_canonical_graph(
        state=state, production_spec=spec,
        capability_requirements=[{"capability_id": "TEXT_GENERATION", "state": "PLANNABLE"}],
        project={"project_id": "p1", "digest": "p"},
        shots=[{"shot_id": "shot-1", "digest": "sh"}],
    )
    impact = cinematic_production_os.dependency_impact(
        organization_id=1, graph=graph, changed_id="shot-1", changed_kind="shot"
    )
    assert impact["policy"]["regenerate_affected_only"] is True
    assert impact["policy"]["full_project_regeneration"] is False
