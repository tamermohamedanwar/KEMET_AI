from __future__ import annotations

from hashlib import sha256
from pathlib import Path

from app.services.runtime_verification_bridge import runtime_verification_bridge


def _bundle(tmp_path: Path, downloaded: bool = True) -> dict:
    checkpoint = tmp_path / "model.safetensors"
    checkpoint.write_bytes(b"verified-model")
    data = {
        "model_id": "kemet-test-video", "model_version": "1.0", "model_family": "test-video", "modality": "TEXT_TO_VIDEO",
        "checkpoint_uri": str(checkpoint), "checkpoint_status": "LOCAL_VERIFIED" if downloaded else "NOT_DOWNLOADED",
        "checkpoint_digest": sha256(checkpoint.read_bytes()).hexdigest(), "commercial_use": True,
        "license_evidence": {"verified": True, "license": "test"}, "hardware_requirements": {}, "benchmark_evidence": [],
    }
    return data


def _runtime(healthy: bool = True) -> dict:
    return {
        "runtime_id": "kemet-test-runtime", "runtime_version": "1.0", "framework": "test", "backend": "cpu", "platform": "linux",
        "health_status": "READY" if healthy else "FAILED", "health_evidence": {"verified": healthy},
        "commercial_use": True, "license_evidence": {"verified": True, "license": "test"},
    }


def _hardware() -> dict:
    return {"ram_gb": 4, "disk_free_gb": 20, "vram_gb": [], "cuda": {"available": False}, "architecture": "x86_64"}
def test_candidate_without_checkpoint_is_blocked(tmp_path):
    out = runtime_verification_bridge.verify(bundle=_bundle(tmp_path, False), runtime=_runtime(), hardware=_hardware())
    assert out["status"] == "BLOCKED"
    assert out["verification"]["checkpoint_verified"] is False
    assert "checkpoint_not_verified" in out["failures"]


def test_checkpoint_digest_mismatch_fails_closed(tmp_path):
    bundle = _bundle(tmp_path)
    bundle["checkpoint_digest"] = "0" * 64
    out = runtime_verification_bridge.verify(bundle=bundle, runtime=_runtime(), hardware=_hardware())
    assert out["status"] == "BLOCKED"
    assert "checkpoint_digest_mismatch" in out["failures"]


def test_runtime_health_failure_stays_blocked(tmp_path):
    out = runtime_verification_bridge.verify(bundle=_bundle(tmp_path), runtime=_runtime(False), hardware=_hardware())
    assert out["status"] == "BLOCKED"
    assert "runtime_health_unverified" in out["failures"]


def test_no_execution_means_not_executed(tmp_path):
    out = runtime_verification_bridge.verify(bundle=_bundle(tmp_path), runtime=_runtime(), hardware=_hardware())
    assert out["benchmark"]["status"] == "NOT_EXECUTED"
    assert out["verification"]["execution_verified"] is False
def test_success_requires_real_artifact_and_digest(tmp_path):
    out_file = tmp_path / "output.mp4"
    out_file.write_bytes(b"real-artifact")
    out = runtime_verification_bridge.verify(
        bundle=_bundle(tmp_path), runtime=_runtime(), hardware=_hardware(),
        executor=lambda: {"output_path": str(out_file), "provenance": {"test": True}},
    )
    assert out["status"] == "READY"
    assert out["benchmark"]["status"] == "EXECUTED"
    assert out["execution"]["output_digest"] == sha256(out_file.read_bytes()).hexdigest()


def test_provider_identity_never_enters_canonical_model_identity(tmp_path):
    bundle = _bundle(tmp_path)
    bundle["provider_id"] = "provider-secret-name"
    out = runtime_verification_bridge.verify(bundle=bundle, runtime=_runtime(), hardware=_hardware())
    assert "provider_id" not in out["model"]


def test_cpu_only_hunyuan_candidate_cannot_be_ready():
    import json
    candidate = json.loads(Path("instance/production/model_candidates/hunyuanvideo_1_5_candidate.json").read_text())
    out = runtime_verification_bridge.verify(bundle=candidate["model"], runtime=_runtime(), hardware={"ram_gb": 3.6, "disk_free_gb": 50, "vram_gb": [], "cuda": {"available": False}, "architecture": "aarch64"})
    assert out["status"] == "BLOCKED"
    assert "checkpoint_not_verified" in out["failures"]
    assert "cuda_unavailable" in out["failures"]


def test_evidence_is_digest_bound_and_secret_free(tmp_path):
    out = runtime_verification_bridge.verify(bundle=_bundle(tmp_path, False), runtime=_runtime(), hardware=_hardware())
    assert out["evidence_digest"]
    assert "secret" not in repr(out).lower()
    assert out["governance"]["mcp"] is False
