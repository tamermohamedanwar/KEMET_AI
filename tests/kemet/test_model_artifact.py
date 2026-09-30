from pathlib import Path

from app.core.runtime.model_artifact import atomic_download_target, is_valid_model, remove_invalid_model


def test_rejects_partial_model(tmp_path, monkeypatch):
    monkeypatch.setenv("KEMET_WHISPER_MODEL_DIR", str(tmp_path))
    path = tmp_path / "ggml-base.bin"
    path.write_bytes(b"partial")
    assert not is_valid_model(path, "base")
    assert remove_invalid_model("base")
    assert not path.exists()


def test_accepts_sufficient_model_size(tmp_path):
    path = tmp_path / "ggml-tiny.bin"
    path.write_bytes(b"x" * (70 * 1024 * 1024))
    assert is_valid_model(path, "tiny")


def test_download_target_is_partial_and_not_final(tmp_path, monkeypatch):
    monkeypatch.setenv("KEMET_WHISPER_MODEL_DIR", str(tmp_path))
    target = atomic_download_target("base")
    assert target.exists()
    assert target.suffix == ".partial"
    assert not (tmp_path / "ggml-base.bin").exists()


def test_accepts_string_model_path(tmp_path):
    path = tmp_path / "ggml-tiny.bin"
    path.write_bytes(b"x" * (70 * 1024 * 1024))
    assert is_valid_model(str(path), "tiny")
