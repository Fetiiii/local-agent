from __future__ import annotations

from pathlib import Path
from typing import Dict, Any

from PyPDF2 import PdfReader

from backend.utils.validators import ensure_file_exists, validate_extension
from backend.parsing.text_cleaner import clean_text, excerpt


def parse_pdf(path: str | Path, max_pages: int = 5) -> Dict[str, Any]:
    """
    Extract text from PDF safely.
    - Reads up to `max_pages` to avoid very large files.
    - Cleans whitespace/control chars.
    """
    if max_pages <= 0:
        raise ValueError("max_pages must be positive")

    validate_extension(path, {".pdf"})
    pdf_path = ensure_file_exists(path)
    reader = PdfReader(str(pdf_path))
    texts = []
    for idx, page in enumerate(reader.pages):
        if idx >= max_pages:
            break
        try:
            raw = page.extract_text() or ""
        except Exception:
            raw = ""
        cleaned = clean_text(raw)
        if cleaned:
            texts.append(f"[p{idx + 1}] {cleaned}")

    content = "\n\n".join(texts)
    return {
        "path": str(pdf_path),
        "page_count": len(reader.pages),
        "pages_read": min(max_pages, len(reader.pages)),
        "content": content,
        "preview": excerpt(content, max_chars=1200),
    }
