from app.services.generation_router import generation_router


def shot():
    return {"shot_id": "s1", "canonical_shot_digest": "digest-1", "high_end_cinematic": True}


def provider(provider_id, ready=True):
    return {
        "provider_id": provider_id, "model": provider_id + "-model", "configured": ready,
        "healthy": ready, "available": ready, "capabilities": ["VIDEO_GENERATION"],
        "features": ["cinematic"], "capacity": {"in_flight": 0, "max_concurrency": 1, "queue_depth": 0, "max_queue_depth": 10},
    }


def test_router_only_selects_capacity_ready_provider():
    out = generation_router.route(organization_id=1, shot=shot(), providers=[provider("blocked", False), provider("ready", True)])
    assert out["status"] == "ROUTE_SELECTED"
    assert out["selection"]["provider_id"] == "ready"
    assert out["capacity_gate"]["ready_providers"] == ["ready"]


def test_router_blocks_when_no_provider_has_live_capacity():
    out = generation_router.route(organization_id=1, shot=shot(), providers=[provider("blocked", False)])
    assert out["status"] == "ROUTE_BLOCKED"
    assert out["selection"] is None
    assert out["capacity_gate"]["status"] == "BLOCKED"


def test_content_request_router_consumes_canonical_production_spec_and_blocks_truthfully():
    out = generation_router.route(
        organization_id=1,
        content_intent="commercial",
        production_spec={"content_intent": "commercial", "dialect": "eg"},
        capability_requirements=["TEXT_GENERATION", "VIDEO_GENERATION", "COMPOSITING", "RENDERING"],
    )
    assert out["status"] == "HARDWARE_BLOCKED"
    assert out["selection"] is None
    assert "VIDEO_GENERATION" in out["capability_resolution"]["blocking_capabilities"]
    assert out["governance"]["execution_authority"] is False


def test_content_request_router_normalizes_capability_requirement_records():
    out = generation_router.route(
        organization_id=1,
        content_intent="voice",
        production_spec={"content_intent": "voice", "language": "ar-EG", "dialect": "eg"},
        capability_requirements=[
            {"capability": "TEXT_TO_SPEECH", "required": True},
            {"capability": "VOICE_SYNTHESIS", "required": True},
            {"capability": "COMPOSITING", "required": True},
        ],
    )
    assert out["required_capabilities"] == ["COMPOSITING", "TEXT_TO_SPEECH", "VOICE_SYNTHESIS"]
    assert out["status"] in {"PLAN_ONLY", "EXECUTE_NOW"}


def test_generation_router_accepts_verified_free_capacity_without_making_it_local():
    from app.services.generation_router import GenerationRouter
    router = GenerationRouter()
    snapshot = {"providers": [{
        "provider_id": "free-video", "worker_id": "worker-1", "free": True,
        "status": "READY", "capabilities": ["VIDEO_GENERATION"], "queue_depth": 0,
        "capacity_evidence": {"observed_at": 1000, "attestation_digest": "a", "attestation": {"ready": True}},
    }]}
    out = router.route(organization_id=1, content_intent="video",
        production_spec={"capability_requirements": ["VIDEO_GENERATION"]},
        capability_requirements=["VIDEO_GENERATION"], free_compute_snapshot=snapshot)
    assert out["status"] == "FREE_CAPACITY_READY"
    assert out["selection"]["execution_path"] == "verified_free_worker"
    assert out["governance"]["execution_authority"] is False
    assert out["governance"]["mcp"] is False


def test_generation_router_without_free_capacity_remains_truthful():
    from app.services.generation_router import GenerationRouter
    out = GenerationRouter().route(organization_id=1, content_intent="video",
        production_spec={"capability_requirements": ["VIDEO_GENERATION"]},
        capability_requirements=["VIDEO_GENERATION"], free_compute_snapshot={"providers": []})
    assert out["status"] == "HARDWARE_BLOCKED"
    assert out["selection"] is None
