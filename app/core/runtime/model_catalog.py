from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelSpec:
    name: str
    filename: str
    min_bytes: int
    min_memory_mb: int


MODEL_CATALOG = {
    "tiny": ModelSpec("tiny", "ggml-tiny.bin", 70 * 1024 * 1024, 273),
    "base": ModelSpec("base", "ggml-base.bin", 140 * 1024 * 1024, 388),
}


def get_model_spec(name: str) -> ModelSpec:
    try:
        return MODEL_CATALOG[name]
    except KeyError as exc:
        raise ValueError(f"unsupported_whisper_model:{name}") from exc
