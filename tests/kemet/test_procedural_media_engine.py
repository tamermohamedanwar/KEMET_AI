from pathlib import Path

from app.core.media.render_engine import RenderEngineV1, RenderRequest
from app.services.procedural_media_engine import procedural_media_engine


def test_procedural_engine_is_kemet_owned_and_zero_provider():
    snapshot = procedural_media_engine.snapshot()
    assert snapshot["external_provider_required"] is False
    assert snapshot["paid_provider_required"] is False
    assert snapshot["personal_gpu_required"] is False
    assert snapshot["network"] == "disabled"


def test_control_layer_plan_has_seven_procedural_shots():
    result = procedural_media_engine.build_the_control_layer_plan(
        organization_id=1, output_uri="/tmp/kemet-control-layer.mp4"
    )
    assert result["success"] is True
    plan = result["plan"]
    assert plan["mode"] == "PROCEDURAL_COMPOSITED"
    assert len(plan["shots"]) == 7
    assert sum(x["duration_seconds"] for x in plan["shots"]) == 45
    assert all(x["generation"] == "procedural" for x in plan["shots"])
    assert plan["governance"]["human_approval_required"] is True


def test_render_engine_accepts_kemet_lavfi_source_spec():
    plan = procedural_media_engine.build_the_control_layer_plan(
        organization_id=1, output_uri="/tmp/kemet-control-layer.mp4"
    )["plan"]
    render_plan = RenderEngineV1().plan(RenderRequest(
        organization_id=1,
        input_uri="",
        output_uri=plan["output_uri"],
        duration_seconds=45,
        source_spec=plan["source_spec"],
        audio=False,
    ))
    assert render_plan["source_spec"]["type"] == "lavfi"
    assert render_plan["network"] == "disabled"
    assert render_plan["execution_authority"] is False


def test_render_engine_still_blocks_remote_source_without_source_spec():
    engine = RenderEngineV1()
    try:
        engine.plan(RenderRequest(1, "https://example.com/x.mp4", "/tmp/x.mp4"))
    except ValueError as exc:
        assert str(exc) == "remote_input_blocked"
    else:
        raise AssertionError("expected remote input to remain blocked")
