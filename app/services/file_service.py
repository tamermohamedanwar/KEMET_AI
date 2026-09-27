import os
import uuid

from werkzeug.utils import secure_filename

from app.rag.chunker import split_text
from app.services.document_ingestion import MAX_UPLOAD_BYTES, ingest_saved_file

UPLOAD_FOLDER = os.path.join("instance", "uploads")
os.makedirs(UPLOAD_FOLDER, mode=0o700, exist_ok=True)


def save_file(file):
    safe_name = secure_filename(file.filename or "upload")
    if not safe_name:
        raise ValueError("Invalid filename")

    content_length = getattr(file, "content_length", None)
    if content_length is not None and content_length > MAX_UPLOAD_BYTES:
        raise ValueError("File exceeds the 25 MB upload limit")

    path = os.path.join(
        UPLOAD_FOLDER,
        f"{uuid.uuid4().hex}_{safe_name}",
    )
    file.save(path)

    try:
        result = ingest_saved_file(path, safe_name)
        chunks = split_text(result["text"])
        result["chunks"] = chunks
        result["chunks_count"] = len(chunks)
        return result
    except Exception:
        try:
            os.remove(path)
        except OSError:
            pass
        raise
