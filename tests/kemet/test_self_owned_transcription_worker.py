from app.services.self_owned_transcription_worker import self_owned_transcription_worker
from app.core.media.capability_fabric import media_capability_fabric


def test_transcription_worker_is_self_owned_and_free():
    snap = self_owned_transcription_worker.snapshot(1)
    assert snap["worker_id"] == "kemet_whisper_cpp_local_worker"
    assert snap["cost_classification"] == "SELF_HOSTED"
    assert snap["free"] is True
    assert snap["license"]["verified"] is True


def test_transcription_capability_is_local_ready():
    snap = {x["capability"]: x for x in media_capability_fabric.local_snapshot()}
    assert snap["TRANSCRIPTION"]["status"] == "LOCAL_READY"
    assert media_capability_fabric.resolve_truth("TRANSCRIPTION")["state"] == "READY"


def test_transcription_worker_plan_binds_graph_and_input(tmp_path):
    source = tmp_path / "input.wav"
    source.write_bytes(b"RIFF" + b"x" * 100)
    spec = {"organization_id": 1, "digest": "s" * 64}
    graph = {"digest": "g" * 64, "nodes": [{"id": "generation", "kind": "generation"}]}
    plan = self_owned_transcription_worker.plan(
        organization_id=1,
        input_path=str(source),
        output_path=str(tmp_path / "transcript.json"),
        production_spec=spec,
        graph=graph,
    )
    assert plan["capability"] == "TRANSCRIPTION"
    assert plan["graph_node_id"] == "generation"
    assert len(plan["plan_hash"]) == 64
