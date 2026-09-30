from app.services.autoclip_capability_service import autoclip_capability_service

def test_autoclip_snapshot_is_non_executing(monkeypatch):
    monkeypatch.delenv("KEMET_AUTOCLIP_EXECUTABLE", raising=False)
    snapshot = autoclip_capability_service.snapshot(7)
    assert snapshot["provider"] == "autoclip_local"
    assert snapshot["license"] == "MIT"
    assert snapshot["execution_authority"] is False
    assert snapshot["governance"]["auto_publish"] is False

def test_autoclip_plan_fails_closed_without_runtime(monkeypatch):
    monkeypatch.delenv("KEMET_AUTOCLIP_EXECUTABLE", raising=False)
    monkeypatch.setattr("app.services.autoclip_capability_service.shutil.which", lambda name: None)
    result = autoclip_capability_service.plan(
        organization_id=7,
        input_uri="asset:long-video.mp4",
        language="ar",
        clip_count=5,
    )
    assert result["success"] is False
    assert result["status"] == "runtime_probe_required"
    assert result["plan"]["execution"]["publication"] is False

def test_autoclip_plan_is_deterministic_when_configured(monkeypatch):
    monkeypatch.setenv("KEMET_AUTOCLIP_EXECUTABLE", "/opt/kemet/autoclip")
    monkeypatch.setattr("app.services.autoclip_capability_service.shutil.which",
                        lambda name: "/usr/bin/ffmpeg" if name == "ffmpeg" else ("/usr/bin/ffprobe" if name == "ffprobe" else None))
    kwargs = {"organization_id": 7, "input_uri": "asset:long-video.mp4", "clip_count": 3}
    first = autoclip_capability_service.plan(**kwargs)
    second = autoclip_capability_service.plan(**kwargs)
    assert first["success"] is True
    assert first["plan"]["plan_digest"] == second["plan"]["plan_digest"]
    assert first["plan"]["governance"]["execution_authority"] is False


def test_media_pipeline_exposes_autoclip_as_optional_governed_stage():
    from app.services.media_production_pipeline import media_production_pipeline
    result = media_production_pipeline.build_plan(
        organization_id=7,
        episode={"title": "Long Video", "platforms": ["youtube"]},
        language="ar-EG",
        duration_seconds=90,
        source_video_uri="asset:long-video.mp4",
    )
    assert result["shortform"]["status"] == "runtime_probe_required"
    assert any(stage["stage"] == "shortform" for stage in result["stages"])
    assert result["governance"]["human_approval_required"] is True
    assert result["shortform"]["plan"]["governance"]["auto_publish"] is False


def test_media_pipeline_keeps_autoclip_optional_without_source():
    from app.services.media_production_pipeline import media_production_pipeline
    result = media_production_pipeline.build_plan(
        organization_id=7,
        episode={"title": "Normal Video", "platforms": ["youtube"]},
        language="ar-EG",
        duration_seconds=90,
    )
    assert result["shortform"] is None
    assert any(stage["stage"] == "shortform" and stage["status"] == "optional" for stage in result["stages"])
