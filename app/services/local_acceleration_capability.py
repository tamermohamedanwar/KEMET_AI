from __future__ import annotations

import importlib.util
import os
import platform
import shutil
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AccelerationSnapshot:
    accelerator: str
    available: bool
    backend: str
    device_count: int
    device_names: tuple[str, ...]
    architecture: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "accelerator": self.accelerator,
            "available": self.available,
            "backend": self.backend,
            "device_count": self.device_count,
            "device_names": list(self.device_names),
            "architecture": self.architecture,
            "reason": self.reason,
        }


class LocalAccelerationCapability:
    VERSION = "1.1"
    CAPABILITY_ID = "local_ai_acceleration"
    EXECUTION_AUTHORITY = "none"

    def snapshot(self) -> dict[str, Any]:
        architecture = platform.machine()
        nvidia_smi = shutil.which("nvidia-smi")
        ram_gb = None
        disk_free_gb = None
        try:
            import psutil
            ram_gb = round(psutil.virtual_memory().total / (1024 ** 3), 2)
        except Exception:
            pass
        try:
            disk_free_gb = round(shutil.disk_usage(os.getcwd()).free / (1024 ** 3), 2)
        except Exception:
            pass
        torch_spec = importlib.util.find_spec("torch")
        cuda_available = False
        device_names: tuple[str, ...] = ()
        vram_gb: tuple[float, ...] = ()
        reason = "nvidia_runtime_not_detected"
        if torch_spec is not None:
            try:
                import torch
                cuda_available = bool(torch.cuda.is_available())
                if cuda_available:
                    device_names = tuple(torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count()))
                    vram_gb = tuple(round(torch.cuda.get_device_properties(i).total_memory / (1024 ** 3), 2) for i in range(torch.cuda.device_count()))
                    reason = "torch_cuda_available"
                else:
                    reason = "torch_present_cuda_unavailable"
            except Exception:
                reason = "torch_cuda_probe_failed"
        elif nvidia_smi:
            reason = "nvidia_smi_present_torch_missing"
        return {
            "version": self.VERSION,
            "capability_id": self.CAPABILITY_ID,
            "execution_authority": self.EXECUTION_AUTHORITY,
            "architecture": architecture,
            "ram_gb": ram_gb,
            "disk_free_gb": disk_free_gb,
            "nvidia_smi": bool(nvidia_smi),
            "host_profile": "gpu_ready" if cuda_available else "cpu_only" if architecture else "unknown",
            "vram_gb": list(vram_gb),
            "cuda": AccelerationSnapshot(
                "cuda", cuda_available, "nvidia", len(device_names), device_names, architecture, reason
            ).as_dict(),
            "policy": {
                "optional": True,
                "read_only_probe": True,
                "no_secret_discovery": True,
                "no_provider_execution_authority": True,
                "no_mandatory_runtime_dependency": True,
                "do_not_install_heavy_gpu_stack_automatically": True,
                "production_use_requires_measured_hardware_and_driver_compatibility": True,
            },
        }


local_acceleration_capability = LocalAccelerationCapability()
