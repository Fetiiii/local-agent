from __future__ import annotations

from pathlib import Path


def resolve_path(path: str | Path, base: str | Path | None = None) -> Path:
    """Resolve a path relative to base (or CWD) and return absolute Path."""
    p = Path(path)
    if not p.is_absolute() and base:
        p = Path(base) / p
    return p.expanduser().resolve()


def ensure_within_base(path: Path, base: Path) -> Path:
    """Ensure the path stays within base directory to avoid traversal."""
    path = path.resolve()
    base = base.resolve()
    if base not in path.parents and path != base:
        raise ValueError(f"Path {path} escapes base {base}")
    return path
