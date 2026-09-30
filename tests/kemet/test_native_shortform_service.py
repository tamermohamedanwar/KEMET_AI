from __future__ import annotations

import json

from app.services.native_shortform_service import native_shortform_service


def test_native_shortform_blocks_remote_input():
    result = native_shortform_service.plan(organization_id=1, input_uri="https://example.com/video.mp4")
    assert result["status"] == "blocked"
    assert result["error"] == "local_input_required"
    assert result["governance"]["execution_authority"] is False


def test_native_shortform_snapshot_is_non_executing():
    result = native_shortform_service.snapshot(organization_id=1)
    assert result["capability_id"] == "kemet_native_shortform"
    assert result["network"] == "disabled"
    assert result["execution_authority"] is False


def test_native_shortform_plan_is_deterministic_for_same_file(tmp_path, monkeypatch):
    source = tmp_path / "sample.mp4"
    source.write_bytes(b"placeholder")

    monkeypatch.setattr(native_shortform_service, "_probe", lambda _: {
        "valid": True, "duration": 120.0, "format_name": "mov,mp4,m4a,3gp,3g2,mj2"
    })
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/" + name)
    first = native_shortform_service.plan(organization_id=1, input_uri=str(source))
    second = native_shortform_service.plan(organization_id=1, input_uri=str(source))
    assert first["success"] is True
    assert first["plan"]["plan_digest"] == second["plan"]["plan_digest"]
    assert len(first["plan"]["candidates"]) == 5
    assert first["plan"]["execution"]["approved_only"] is True
    json.dumps(first)


def test_native_shortform_missing_file_fails_closed(tmp_path):
    result = native_shortform_service.plan(organization_id=1, input_uri=str(tmp_path / "missing.mp4"))
    assert result["status"] == "input_not_found"


def test_transcript_scoring_is_deterministic(tmp_path, monkeypatch):
    source = tmp_path / "video.mp4"
    source.write_bytes(b"video")
    monkeypatch.setattr(native_shortform_service, "_probe", lambda _: {"valid": True, "duration": 120.0, "format_name": "mp4"})
    transcript = [
        {"start": 10, "end": 15, "text": "short"},
        {"start": 70, "end": 78, "text": "This is a much longer segment with enough semantic content to score higher."},
    ]
    first = native_shortform_service.plan(organization_id=1, input_uri=str(source), transcript=transcript)
    second = native_shortform_service.plan(organization_id=1, input_uri=str(source), transcript=transcript)
    assert first["plan"]["candidates"] == second["plan"]["candidates"]
    assert first["plan"]["candidates"][0]["selection"] == "transcript_scored"
