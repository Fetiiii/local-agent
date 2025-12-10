from __future__ import annotations

from pathlib import Path
from typing import Iterable


def validate_extension(path: str | Path, allowed: Iterable[str]) -> None:
    ext = Path(path).suffix.lower()
    if ext not in allowed:
        raise ValueError(f"Unsupported file type: {ext}")


def ensure_file_exists(path: str | Path) -> Path:
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"File not found: {p}")
    return p
