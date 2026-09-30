from app.core.runtime.runtime_cleanup import cleanup_partial_models, cleanup_transient_files


def test_cleanup_partial_models(tmp_path):
    (tmp_path / ".ggml-base.bin.123.partial").write_bytes(b"x")
    (tmp_path / "keep.bin").write_bytes(b"x")
    assert cleanup_partial_models(tmp_path) == 1
    assert not (tmp_path / ".ggml-base.bin.123.partial").exists()
    assert (tmp_path / "keep.bin").exists()


def test_cleanup_transient_files(tmp_path):
    for name in ("a.wav", "b.partial", "c.tmp"):
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "keep.txt").write_bytes(b"x")
    assert cleanup_transient_files(tmp_path) == 3
    assert (tmp_path / "keep.txt").exists()
