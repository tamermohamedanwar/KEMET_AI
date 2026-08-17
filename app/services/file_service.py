import os

from app.services.file_reader import FileReader
from app.rag.chunker import split_text

UPLOAD_FOLDER = "app/static/uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def save_file(file):
    path = os.path.join(UPLOAD_FOLDER, file.filename)

    file.save(path)

    text = FileReader.read(path)
    chunks = split_text(text)

    return {
        "path": path,
        "text": text,
        "chunks": chunks,
        "chunks_count": len(chunks),
    }
