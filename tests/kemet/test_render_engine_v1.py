from pathlib import Path
from app.core.media.render_engine import RenderEngineV1, RenderRequest

def test_render_plan_is_local_and_non_executing():
    e=RenderEngineV1()
    p=e.plan(RenderRequest(1,"/tmp/in.mp4","/tmp/out.mp4"))
    assert p["schema"]=="kemet.render_plan.v1"
    assert p["network"]=="disabled"
    assert p["execution_authority"] is False
    assert p["governance"]["mcp"] is False

def test_remote_paths_blocked():
    e=RenderEngineV1()
    for field in ("input_uri","output_uri"):
        kwargs={"organization_id":1,"input_uri":"/tmp/in.mp4","output_uri":"/tmp/out.mp4"}
        kwargs[field]="https://example.com/media.mp4"
        try: e.plan(RenderRequest(**kwargs))
        except ValueError as exc: assert str(exc).endswith("_blocked")
        else: raise AssertionError("expected blocked path")

def test_remote_audio_blocked():
    e=RenderEngineV1()
    p=e.plan(RenderRequest(1,"/tmp/in.mp4","/tmp/out.mp4",audio_uri="https://example.com/voice.wav"))
    assert p["audio_uri"].startswith("https://")
    result=e.render(p, approval=True, execution_authorization={"_execution_action":"media_render","_approved_execution":True,"gate_handoff":True})
    assert result["executed"] is False
    assert result["error"]=="remote_audio_blocked"

def test_render_requires_approval():
    e=RenderEngineV1()
    p=e.plan(RenderRequest(1,"/tmp/in.mp4","/tmp/out.mp4"))
    result=e.render(p)
    assert result["executed"] is False
    assert result["error"]=="human_approval_required"
