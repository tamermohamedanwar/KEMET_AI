from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResourceDecision:
    allowed: bool
    reason: str
    available_mb: int
    required_mb: int
    model: str


_MODEL_MEMORY_MB = {
    "tiny": 273,
    "base": 388,
    "small": 852,
}


def available_memory_mb() -> int:
    try:
        text = Path("/proc/meminfo").read_text(encoding="utf-8")
        values = {}
        for line in text.splitlines():
            key, value = line.split(":", 1)
            values[key] = int(value.strip().split()[0])
        available_kb = values.get("MemAvailable", values.get("MemFree", 0))
        return available_kb // 1024
    except (OSError, ValueError):
        return 0


def choose_model(preferred: str | None = None, available_mb_value: int | None = None) -> str:
    available = available_memory_mb() if available_mb_value is None else available_mb_value
    requested = (preferred or os.getenv("KEMET_WHISPER_MODEL", "auto")).strip().lower()
    if requested != "auto" and requested in _MODEL_MEMORY_MB:
        if available >= _MODEL_MEMORY_MB[requested] + 256:
            return requested
    for model in ("small", "base", "tiny"):
        if available >= _MODEL_MEMORY_MB[model] + 256:
            return model
    return ""


def decide(model: str, available_mb_value: int | None = None) -> ResourceDecision:
    available = available_memory_mb() if available_mb_value is None else available_mb_value
    required = _MODEL_MEMORY_MB.get(model, 512) + 256
    return ResourceDecision(
        allowed=available >= required,
        reason="resources_ready" if available >= required else "insufficient_memory",
        available_mb=available,
        required_mb=required,
        model=model,
    )
