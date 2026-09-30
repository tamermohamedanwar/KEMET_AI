from app.core.media.open_video_catalog import catalog_snapshot, eligible, runtime


def test_catalog_contains_open_video_targets():
    snap = catalog_snapshot()
    ids = {x["provider_id"] for x in snap["runtimes"]}
    assert "wan2_1_local" in ids
    assert "hunyuanvideo_1_5_local" in ids
    assert "comfyui_local" in ids
    assert snap["mcp"] is False


def test_runtime_requires_cuda_for_gpu_models():
    assert eligible("wan2_1_local", gpu_vram_gb=24, cuda=False) is False
    assert eligible("wan2_1_local", gpu_vram_gb=8, cuda=True) is False
    assert eligible("wan2_1_local", gpu_vram_gb=8.2, cuda=True) is True


def test_unknown_runtime_is_rejected():
    try:
        runtime("not-a-real-runtime")
    except KeyError as exc:
        assert str(exc) == "'unknown_open_video_runtime'"
    else:
        raise AssertionError("unknown runtime must be rejected")
