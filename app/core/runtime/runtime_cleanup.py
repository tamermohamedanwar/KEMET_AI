from __future__ import annotations

from pathlib import Path


def cleanup_partial_models(model_dir: Path) -> int:
    removed = 0
    if not model_dir.exists():
        return 0
    for path in model_dir.glob(".*.partial"):
        if path.is_file():
            path.unlink(missing_ok=True)
            removed += 1
    return removed


def cleanup_transient_files(work_dir: Path) -> int:
    removed = 0
    if not work_dir.exists():
        return 0
    for pattern in ("*.wav", "*.partial", "*.tmp"):
        for path in work_dir.glob(pattern):
            if path.is_file():
                path.unlink(missing_ok=True)
                removed += 1
    return removed
