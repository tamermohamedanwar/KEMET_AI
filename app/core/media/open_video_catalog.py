"""Catalog of local/open video runtimes that can plug into Kemet Media Factory.

This catalog records integration targets only. It does not download weights or
claim that a runtime is usable on the current device until hardware is verified.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class OpenVideoRuntime:
    provider_id: str
    project_url: str
    capabilities: tuple[str, ...]
    minimum_gpu_vram_gb: float | None
    target_resolution: str
    license_note: str
    readiness: str

OPEN_VIDEO_RUNTIMES = (
    OpenVideoRuntime(
        provider_id="wan2_1_local",
        project_url="https://github.com/Wan-Video/Wan2.1",
        capabilities=("TEXT_TO_VIDEO", "IMAGE_TO_VIDEO", "VIDEO_EDITING"),
        minimum_gpu_vram_gb=8.2,
        target_resolution="480p/5s baseline",
        license_note="Review model and repository licenses before commercial distribution.",
        readiness="candidate",
    ),
    OpenVideoRuntime(
        provider_id="hunyuanvideo_1_5_local",
        project_url="https://github.com/Tencent-Hunyuan/HunyuanVideo-1.5",
        capabilities=("TEXT_TO_VIDEO", "IMAGE_TO_VIDEO"),
        minimum_gpu_vram_gb=14.0,
        target_resolution="480p baseline; higher-resolution stages available",
        license_note="Tencent Hunyuan Community License; commercial use requires license review.",
        readiness="candidate",
    ),
    OpenVideoRuntime(
        provider_id="comfyui_local",
        project_url="https://github.com/comfyanonymous/ComfyUI",
        capabilities=("WORKFLOW_ORCHESTRATION", "IMAGE_TO_VIDEO", "TEXT_TO_VIDEO"),
        minimum_gpu_vram_gb=None,
        target_resolution="runtime-dependent",
        license_note="Runtime/orchestrator; each model and custom node has its own license.",
        readiness="integration_target",
    ),
)

def catalog_snapshot() -> dict[str, Any]:
    return {
        "version": "1.0",
        "runtimes": [
            {
                "provider_id": x.provider_id,
                "project_url": x.project_url,
                "capabilities": list(x.capabilities),
                "minimum_gpu_vram_gb": x.minimum_gpu_vram_gb,
                "target_resolution": x.target_resolution,
                "license_note": x.license_note,
                "readiness": x.readiness,
            }
            for x in OPEN_VIDEO_RUNTIMES
        ],
        "execution_authority": False,
        "external_execution": False,
        "mcp": False,
    }
def runtime(provider_id: str) -> OpenVideoRuntime:
    for item in OPEN_VIDEO_RUNTIMES:
        if item.provider_id == provider_id:
            return item
    raise KeyError("unknown_open_video_runtime")


def eligible(provider_id: str, *, gpu_vram_gb: float | None, cuda: bool) -> bool:
    item = runtime(provider_id)
    if not cuda:
        return False
    if item.minimum_gpu_vram_gb is None:
        return True
    return gpu_vram_gb is not None and gpu_vram_gb >= item.minimum_gpu_vram_gb
