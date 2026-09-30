from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

MODEL_SPECS = {
    "tiny": {"filename": "ggml-tiny.bin", "min_bytes": 70 * 1024 * 1024},
    "base": {"filename": "ggml-base.bin", "min_bytes": 140 * 1024 * 1024},
    "small": {"filename": "ggml-small.bin", "min_bytes": 400 * 1024 * 1024},
}

def model_path(model: str) -> Path:
    root = Path(os.getenv("KEMET_WHISPER_MODEL_DIR", ".kemet_runtime/whisper_cpp/models"))
    return root / MODEL_SPECS[model]["filename"]

def is_valid_model(path: Path | str, model: str) -> bool:
    try:
        path = Path(path)
        return path.is_file() and path.stat().st_size >= MODEL_SPECS[model]["min_bytes"]
    except (OSError, KeyError):
        return False

def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()

def remove_invalid_model(model: str) -> bool:
    path = model_path(model)
    if not path.exists():
        return False
    if is_valid_model(path, model):
        return False
    path.unlink(missing_ok=True)
    return True

def atomic_download_target(model: str) -> Path:
    path = model_path(model)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".partial", dir=path.parent)
    os.close(fd)
    return Path(tmp)
