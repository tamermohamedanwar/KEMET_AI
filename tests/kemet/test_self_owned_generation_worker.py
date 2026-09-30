from app.services.self_owned_generation_worker import self_owned_generation_worker
from app.services.cinematic_production_os import cinematic_production_os


def _spec(org=1):
    return {"schema": "kemet.production.spec.v1", "organization_id": org, "content_intent": "voice", "digest": "s" * 64}


def _graph(org=1):
    return {"organization_id": org, "digest": "g" * 64, "nodes": [{"id": "generation", "kind": "generation"}]}


def test_worker_snapshot_is_self_owned_free_and_local():
    snap = self_owned_generation_worker.snapshot(1)
    assert snap["worker_id"] == "kemet_sherpa_onnx_nabra_local_worker"
    assert snap["cost_classification"] == "SELF_HOSTED"
    assert snap["free"] is True
    assert snap["execution_authority"] is False


def test_worker_plan_accepts_verified_nabra_runtime():
    plan = self_owned_generation_worker.plan(
        organization_id=1,
        text="اختبار كيمت",
        output_path=".kemet_runtime/nabra_tts/artifacts/test-plan.wav",
        production_spec=_spec(),
        graph=_graph(),
    )
    assert plan["worker_id"] == "kemet_sherpa_onnx_nabra_local_worker"
    assert plan["runtime"] == "sherpa-onnx"
    assert plan["runtime_version"] == "1.13.8"


def test_worker_plan_rejects_missing_generation_node():
    try:
        self_owned_generation_worker.plan(
            organization_id=1, text="x", output_path="/tmp/x.wav",
            production_spec=_spec(), graph={"organization_id": 1, "digest": "g" * 64, "nodes": []},
        )
    except ValueError as exc:
        assert str(exc) == "generation_graph_node_required"
    else:
        raise AssertionError("expected generation_graph_node_required")


def test_canonical_graph_contains_generation_node():
    state = cinematic_production_os.build_state(organization_id=1, project_id="p", stage="generation")
    graph = cinematic_production_os.build_canonical_graph(
        state=state,
        production_spec=_spec(),
        capability_requirements=[{"capability": "TEXT_TO_SPEECH", "state": "READY"}],
    )
    node_ids = {n["id"] for n in graph["nodes"]}
    assert "generation" in node_ids
    assert ["routing", "generation"] in graph["edges"]


def test_worker_action_requires_canonical_execution():
    from app.automation.action_registry import registry
    result = registry.execute("kemet_self_owned_tts_generate", {})
    assert result["status"] == "blocked"
    assert result["error"] == "canonical_execution_required"
