from app.services.media_production_pipeline import MediaProductionPipeline


def test_media_pipeline_exposes_production_studio_plan():
    plan = MediaProductionPipeline().build_plan(
        organization_id=1,
        episode={
            "title": "Mendes Episode",
            "platforms": ["youtube", "tiktok", "instagram"],
            "reference_uri": "https://example.test/reference",
        },
    )
    assert plan["production_studio"]["plan_digest"]
    assert plan["production_studio"]["reference"]["provided"] is True
    assert plan["production_studio"]["governance"]["human_approval_required"] is True


def test_build_transcribed_shortform_plan_passes_transcript_to_planner(monkeypatch, tmp_path):
    from app.services.media_production_pipeline import MediaProductionPipeline

    source = tmp_path / "video.mp4"
    source.write_bytes(b"video")
    transcript = [{"start": 4.0, "end": 9.0, "text": "A useful segment"}]
    monkeypatch.setattr(
        "app.services.media_production_pipeline.native_transcription_service.transcribe",
        lambda **kwargs: {"success": True, "status": "transcribed", "transcript": transcript, "transcript_digest": "abc"},
    )
    captured = {}
    monkeypatch.setattr(
        "app.services.media_production_pipeline.native_shortform_service.plan",
        lambda **kwargs: captured.update(kwargs) or {
            "success": True,
            "status": "planned",
            "organization_id": 1,
            "plan_digest": "b" * 64,
            "candidates": [{"index": 1, "start": 4.0, "duration": 5.0, "selection": "transcript_scored"}],
        },
    )
    result = MediaProductionPipeline().build_transcribed_shortform_plan(
        organization_id=1, input_uri=str(source), language="ar", clip_count=3, aspect_ratio="9:16"
    )
    assert result["success"] is True
    assert captured["transcript"] == transcript
    assert result["transcription"]["segment_count"] == 1
    assert result["status"] == "transcribed_shortform_approval_ready"
    assert result["approval_packet"]["approval"]["status"] == "PENDING_HUMAN_APPROVAL"
    assert result["approval_packet"]["governance"]["execution_authority"] is False
    assert result["approval_packet"]["governance"]["external_publication"] is False


def test_build_transcribed_shortform_plan_fails_closed_when_transcription_blocked(monkeypatch, tmp_path):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video")
    monkeypatch.setattr(
        "app.services.media_production_pipeline.native_transcription_service.transcribe",
        lambda **kwargs: {"success": False, "status": "model_required", "error": "whisper_model_unavailable"},
    )
    result = __import__("app.services.media_production_pipeline", fromlist=["media_production_pipeline"]).media_production_pipeline.build_transcribed_shortform_plan(
        organization_id=1, input_uri=str(source)
    )
    assert result["success"] is False
    assert result["status"] == "transcription_blocked"
    assert result["transcription"]["error"] == "whisper_model_unavailable"
