from pathlib import Path
from app.core.media.qa_gate import media_qa_gate_v1

def test_qa_passes_real_video_artifact(tmp_path):
    source = tmp_path / "source.mp4"
    import subprocess
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y","-f","lavfi","-i","color=c=black:s=320x240:d=1","-f","lavfi","-i","anullsrc=r=44100:cl=mono","-t","1","-c:v","libx264","-c:a","aac",str(source)], check=True)
    digest = media_qa_gate_v1._file_digest(source)
    artifact = {"artifact_id":"a1","organization_id":7,"kind":"video","mime_type":"video/mp4","digest":digest,"uri":str(source)}
    result = media_qa_gate_v1.inspect(organization_id=7, artifact=artifact)
    assert result["status"] == "PASS"
    assert all(result["checks"].values())
    assert result["governance"]["mcp"] is False
    assert result["execution_authority"] is False

def test_qa_blocks_tenant_mismatch(tmp_path):
    artifact = {"artifact_id":"a1","organization_id":8,"kind":"video","mime_type":"video/mp4","digest":"x","uri":str(tmp_path/"x.mp4")}
    try:
        media_qa_gate_v1.inspect(organization_id=7, artifact=artifact)
    except ValueError as exc:
        assert str(exc) == "artifact_tenant_mismatch"
    else:
        raise AssertionError("expected tenant mismatch")

def test_qa_blocks_remote_artifact():
    result = media_qa_gate_v1.inspect(organization_id=7, artifact={
        "artifact_id":"a1","organization_id":7,"kind":"video","mime_type":"video/mp4",
        "digest":"x","uri":"https://example.invalid/a.mp4"})
    assert result["status"] == "BLOCKED"
    assert result["error"] == "local_artifact_required"
