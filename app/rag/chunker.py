def split_text(text: str, chunk_size: int = 500, overlap: int = 100):
    text = text.strip()

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])

        if end >= len(text):
            break

        start = end - overlap

    return chunks


class TextChunker:
    def __init__(self, chunk_size=500, overlap=100):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def split(self, text: str):
        return split_text(
            text,
            chunk_size=self.chunk_size,
            overlap=self.overlap
        )
