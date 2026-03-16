"""
backend/tools/file_editing/security/syntax_validator.py
---------------------------------------------------------
Pre-write syntax validation for common file types.

Validates content before it is ever committed to disk so that the agent
cannot accidentally write broken Python, malformed JSON, invalid YAML, or
unparseable TOML into the project.

Supported extensions and their parsers
---------------------------------------
.py   → ast.parse          (stdlib)
.json → json.loads         (stdlib)
.yaml / .yml → yaml.safe_load (pyyaml)
.toml → tomllib.loads      (stdlib ≥ 3.11; tomli fallback for 3.9/3.10)

Unknown extensions are silently skipped (not all text files have parseable
syntax and we don't want to block plain .txt, .md, etc.).
"""

import ast
import json
import sys
from pathlib import Path
from typing import Optional


# ── tomllib compatibility ──────────────────────────────────────────────────────
if sys.version_info >= (3, 11):
    import tomllib  # stdlib from 3.11
else:
    try:
        import tomllib  # type: ignore[no-redef]
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-redef]
        except ImportError:
            tomllib = None  # type: ignore[assignment]


# ── pyyaml ────────────────────────────────────────────────────────────────────
try:
    import yaml  # type: ignore[import-untyped]
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


class SyntaxValidationError(ValueError):
    """
    Raised when pre-write syntax validation fails.

    Attributes
    ----------
    file_ext:   Extension that was being validated (e.g. '.py').
    line:       Line number of the error, if available.
    column:     Column number of the error, if available.
    detail:     Human-readable parser error message.
    """

    def __init__(
        self,
        message: str,
        file_ext: str = "",
        line: Optional[int] = None,
        column: Optional[int] = None,
        detail: str = "",
    ) -> None:
        super().__init__(message)
        self.file_ext = file_ext
        self.line = line
        self.column = column
        self.detail = detail

    def __str__(self) -> str:  # pragma: no cover
        parts = [super().__str__()]
        if self.line is not None:
            parts.append(f"line {self.line}")
        if self.column is not None:
            parts.append(f"col {self.column}")
        if self.detail:
            parts.append(self.detail)
        return " | ".join(parts)


# ── Validators ─────────────────────────────────────────────────────────────────

def _validate_python(content: str) -> None:
    """Parse *content* as Python source using the stdlib `ast` module."""
    try:
        ast.parse(content)
    except SyntaxError as exc:
        raise SyntaxValidationError(
            f"Python syntax error: {exc.msg}",
            file_ext=".py",
            line=exc.lineno,
            column=exc.offset,
            detail=exc.text or "",
        ) from exc


def _validate_json(content: str) -> None:
    """Parse *content* as JSON."""
    try:
        json.loads(content)
    except json.JSONDecodeError as exc:
        raise SyntaxValidationError(
            f"JSON syntax error: {exc.msg}",
            file_ext=".json",
            line=exc.lineno,
            column=exc.colno,
            detail=str(exc),
        ) from exc


def _validate_yaml(content: str) -> None:
    """Parse *content* as YAML (requires pyyaml)."""
    if not _YAML_AVAILABLE:
        # pyyaml not installed — skip silently rather than blocking all writes.
        return
    try:
        yaml.safe_load(content)
    except yaml.YAMLError as exc:
        line: Optional[int] = None
        col: Optional[int] = None
        if hasattr(exc, "problem_mark") and exc.problem_mark:
            line = exc.problem_mark.line + 1
            col = exc.problem_mark.column + 1
        raise SyntaxValidationError(
            f"YAML syntax error",
            file_ext=".yaml",
            line=line,
            column=col,
            detail=str(exc),
        ) from exc


def _validate_toml(content: str) -> None:
    """Parse *content* as TOML (requires tomllib/tomli)."""
    if tomllib is None:
        # tomllib/tomli not available — skip silently.
        return
    try:
        tomllib.loads(content)
    except Exception as exc:  # tomllib raises TOMLDecodeError
        # Extract line info if the exception carries it (Python 3.11+ does).
        line: Optional[int] = getattr(exc, "lineno", None)
        col: Optional[int] = getattr(exc, "colno", None)
        raise SyntaxValidationError(
            f"TOML syntax error",
            file_ext=".toml",
            line=line,
            column=col,
            detail=str(exc),
        ) from exc


# ── Public API ─────────────────────────────────────────────────────────────────

_VALIDATORS = {
    ".py": _validate_python,
    ".json": _validate_json,
    ".yaml": _validate_yaml,
    ".yml": _validate_yaml,
    ".toml": _validate_toml,
}


def validate_syntax(path: Path | str, content: str) -> None:
    """
    Validate *content* before writing it to *path*.

    Dispatches to the appropriate parser based on the file extension.
    Extensions not in the supported list are silently skipped.

    Parameters
    ----------
    path:    File path (used only to determine the extension).
    content: Text content to validate.

    Raises
    ------
    SyntaxValidationError: if the content fails the parser for its extension.
    """
    ext = Path(path).suffix.lower()
    validator = _VALIDATORS.get(ext)
    if validator is not None:
        validator(content)
