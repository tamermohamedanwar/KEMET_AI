from io import BytesIO
from pathlib import Path

import pytest

from app.services import document_ingestion
from app.services import file_service
from app.services.file_service import save_file


class Upload:
    def __init__(self, filename, payload):
        self.filename = filename
        self.payload = payload

    def save(self, path):
        Path(path).write_bytes(self.payload)


def test_ingestion_uses_markitdown_when_available(tmp_path, monkeypatch):
    source = tmp_path / "report.pdf"
    source.write_bytes(b"placeholder")
    monkeypatch.setattr(
        document_ingestion,
        "_markitdown_convert",
        lambda path: "# Report\n\n| A | B |\n|---|---|\n| 1 | 2 |",
    )

    result = document_ingestion.ingest_saved_file(
        str(source), "report.pdf"
    )

    assert result["converter"] == "markitdown"
    assert result["text"].startswith("# Report")
    assert len(result["content_sha256"]) == 64


def test_ingestion_rejects_unsupported_type(tmp_path):
    source = tmp_path / "payload.exe"
    source.write_bytes(b"bad")

    with pytest.raises(ValueError, match="Unsupported file type"):
        document_ingestion.ingest_saved_file(
            str(source), "payload.exe"
        )


def test_ingestion_enforces_size_limit(tmp_path):
    source = tmp_path / "large.txt"
    source.write_bytes(b"x" * (document_ingestion.MAX_UPLOAD_BYTES + 1))

    with pytest.raises(ValueError, match="25 MB"):
        document_ingestion.ingest_saved_file(
            str(source), "large.txt"
        )


def test_upload_storage_is_outside_web_static_tree():
    upload_path = Path(file_service.UPLOAD_FOLDER).resolve()
    static_path = Path("app/static").resolve()
    assert static_path not in upload_path.parents


def test_save_file_uses_safe_unique_storage_name(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.services.file_service.UPLOAD_FOLDER",
        str(tmp_path),
    )
    monkeypatch.setattr(
        "app.services.file_service.ingest_saved_file",
        lambda path, name: {
            "path": path,
            "filename": name,
            "file_type": "txt",
            "file_size": 5,
            "text": "hello",
        },
    )

    result = save_file(Upload("../../secret.txt", b"hello"))

    assert result["filename"] == "secret.txt"
    assert Path(result["path"]).parent == tmp_path
    assert Path(result["path"]).name.endswith("_secret.txt")
    assert result["chunks_count"] >= 1


def test_ingestion_rejects_symlink(tmp_path):
    source = tmp_path / "target.txt"
    source.write_text("hello")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(source)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable")

    with pytest.raises(ValueError, match="Symlink"):
        document_ingestion.ingest_saved_file(str(link), "link.txt")


def test_ingestion_rejects_empty_extraction(tmp_path, monkeypatch):
    source = tmp_path / "empty.txt"
    source.write_text("hello")
    monkeypatch.setattr(
        document_ingestion,
        "_fallback_convert",
        lambda path: "   ",
    )

    with pytest.raises(ValueError, match="No extractable text"):
        document_ingestion.ingest_saved_file(str(source), "empty.txt")
