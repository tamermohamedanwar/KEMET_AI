from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from werkzeug.utils import secure_filename

from app.services.file_reader import FileReader

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
SUPPORTED_EXTENSIONS = {
    ".csv", ".docx", ".html", ".json", ".pdf", ".pptx",
    ".txt", ".xlsx", ".xml",
}
MARKITDOWN_EXTENSIONS = {
    ".docx", ".html", ".pdf", ".pptx", ".txt",
}


def _markitdown_convert(path: str) -> str | None:
    try:
        from markitdown import MarkItDown
    except ImportError:
        return None

    try:
        converter = MarkItDown(enable_plugins=False)
        result = converter.convert_local(path)
        return result.markdown or result.text_content or ""
    except Exception:
        return None


def _fallback_convert(path: str) -> str:
    return FileReader.read(path)


def _validate_saved_file(file_path: Path, suffix: str) -> int:
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")
    if not file_path.exists() or not file_path.is_file():
        raise ValueError("Uploaded file is unavailable")
    if file_path.is_symlink():
        raise ValueError("Symlink uploads are not allowed")

    size = file_path.stat().st_size
    if size > MAX_UPLOAD_BYTES:
        raise ValueError("File exceeds the 25 MB upload limit")
    return size


def ingest_saved_file(path: str, original_filename: str) -> dict[str, Any]:
    safe_name = secure_filename(original_filename or Path(path).name)
    if not safe_name:
        raise ValueError("Invalid filename")

    suffix = Path(safe_name).suffix.lower()
    raw_path = Path(path)
    if raw_path.is_symlink():
        raise ValueError("Symlink uploads are not allowed")
    file_path = raw_path.resolve()
    size = _validate_saved_file(file_path, suffix)

    text = None
    converter = "file_reader"
    if suffix in MARKITDOWN_EXTENSIONS:
        text = _markitdown_convert(str(file_path))
        if text is not None:
            converter = "markitdown"

    if text is None:
        text = _fallback_convert(str(file_path))

    normalized = (text or "").strip()
    if not normalized:
        raise ValueError("No extractable text was found in the uploaded file")

    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return {
        "path": str(file_path),
        "filename": safe_name,
        "file_type": suffix.lstrip(".") or "unknown",
        "file_size": size,
        "text": normalized,
        "converter": converter,
        "content_sha256": digest,
    }
