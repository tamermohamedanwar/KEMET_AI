from pathlib import Path

def extract_text(file_path: str) -> str:
    """
    Temporary text loader.
    Supports .txt now.
    PDF and DOCX will be added later.
    """
    suffix = Path(file_path).suffix.lower()

    if suffix == ".txt":
        return Path(file_path).read_text(
            encoding="utf-8",
            errors="ignore"
        )

    return ""
