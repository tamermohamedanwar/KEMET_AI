from pathlib import Path
import json

from app.services.native_transcription_service import NativeTranscriptionService


def test_snapshot_is_non_executing(monkeypatch):
    monkeypatch.delenv("KEMET_WHISPER_CPP_EXECUTABLE", raising=False)
    result = NativeTranscriptionService().snapshot(1)
    assert result["execution_authority"] is False
    assert result["governance"]["auto_publish"] is False


def test_remote_input_fails_closed():
    result = NativeTranscriptionService().transcribe(organization_id=1, input_uri="https://example.com/a.mp4")
    assert result["success"] is False
    assert result["error"] == "local_input_required"


def test_missing_input_fails_closed(tmp_path: Path):
    result = NativeTranscriptionService().transcribe(organization_id=1, input_uri=str(tmp_path / "missing.mp4"))
    assert result["success"] is False
    assert result["error"] == "input_not_found"


def test_parser_normalizes_segments():
    result = NativeTranscriptionService._parse_json_output('{"transcription":[{"offsets":{"from":1000,"to":2500},"text":" Hello "}]}')
    assert result == [{"start": 1.0, "end": 2.5, "text": "Hello"}]


def test_parse_json_output_reads_whisper_file_shape():
    payload = {"transcription": [{"offsets": {"from": 0, "to": 10500}, "text": " hello world "}]}
    parsed = NativeTranscriptionService._parse_json_output(json.dumps(payload))
    assert parsed == [{"start": 0.0, "end": 10.5, "text": "hello world"}]
