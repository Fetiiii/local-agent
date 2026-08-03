"""
backend/tools/file_editing/file_architect.py
---------------------------------------------
FileArchitectTool — registered as "file_architect".

Creates files and directory trees from a dict of {relative_path: content}.

Safety features
---------------
• All paths resolved through SafePathResolver (confined to DATA_ROOT).
• Atomic writes via atomic_write (no partial files on crash).
• Pre-write syntax validation (.py, .json, .yaml, .toml).
• Refuses to overwrite existing files unless overwrite=True.
• Hard limits: max 20 files per call, max 200 KB per file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.tools.file_editing.config import DATA_ROOT, MAX_FILE_SIZE, MAX_FILES_PER_CALL
from backend.tools.file_editing.logging_config import logger
from backend.tools.file_editing.security.atomic_write import atomic_write, AtomicWriteError
from backend.tools.file_editing.security.path_resolver import SafePathResolver, PathTraversalError
from backend.tools.file_editing.security.syntax_validator import validate_syntax, SyntaxValidationError


class FileArchitectTool:
    """
    Create multiple files atomically inside DATA_ROOT.

    Tool name: ``file_architect``

    run() arguments
    ---------------
    files      : Dict[str, str]  — {relative_path: content}
    overwrite  : bool            — default False; set True to allow replacing files.
    """

    name = "file_architect"
    description = (
        "Create files and directories from a dict {relative_path: content}. "
        "All paths are confined to data/exports. Refuses to overwrite unless overwrite=True. "
        "Runs syntax validation before writing. Limits: 20 files/call, 200 KB/file."
    )

    def __init__(self, root: Optional[Path] = None) -> None:
        self._resolver = SafePathResolver(root or DATA_ROOT)

    # ── Public tool entry-point ────────────────────────────────────────────────

    def run(
        self,
        files: Dict[str, str],
        overwrite: bool = False,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create *files* inside DATA_ROOT.

        Parameters
        ----------
        files:     Mapping of relative file path → text content.
        overwrite: If False (default), skip (with error) any file that already exists.

        Returns
        -------
        Dict with ``text`` summary, ``created`` list, and ``errors`` list.
        """
        created: List[str] = []
        created_paths: List[str] = []   # absolute paths → surfaced as artifacts
        errors: List[str] = []

        # ── Guard: too many files ──────────────────────────────────────────────
        if len(files) > MAX_FILES_PER_CALL:
            return {
                "text": (
                    f"❌ Batch too large: {len(files)} files requested, "
                    f"maximum is {MAX_FILES_PER_CALL} per call."
                ),
                "created": [],
                "errors": [],
            }

        for rel_path, content in files.items():
            result = self._create_single(rel_path, content, overwrite)
            if result["ok"]:
                created.append(rel_path)
                if result.get("path"):
                    created_paths.append(result["path"])
                logger.info("file_architect create %s", rel_path)
            else:
                errors.append(f"{rel_path}: {result['reason']}")
                logger.warning("file_architect skip %s — %s", rel_path, result["reason"])

        summary_parts = [f"✅ Created {len(created)} file(s)."]
        if errors:
            summary_parts.append(f"⚠️ {len(errors)} skipped: {'; '.join(errors)}")

        return {
            "text": " ".join(summary_parts),
            "created": created,
            "errors": errors,
            # Surface created files to the UI artifact panel (HTML preview, etc.).
            "artifacts": created_paths,
        }

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _create_single(
        self,
        rel_path: str,
        content: str,
        overwrite: bool,
    ) -> Dict[str, Any]:
        """Validate path, check limits, validate syntax, then atomic-write."""

        # 1. Path safety
        try:
            target = self._resolver.resolve(rel_path)
        except PathTraversalError as exc:
            return {"ok": False, "reason": str(exc)}

        # 2. Overwrite guard
        if target.exists() and not overwrite:
            return {
                "ok": False,
                "reason": f"File already exists. Pass overwrite=True to replace it.",
            }

        # 3. Size limit (in bytes assuming UTF-8 ≈ len(content))
        size_bytes = len(content.encode("utf-8"))
        if size_bytes > MAX_FILE_SIZE:
            return {
                "ok": False,
                "reason": (
                    f"Content too large ({size_bytes:,} bytes). "
                    f"Maximum is {MAX_FILE_SIZE:,} bytes ({MAX_FILE_SIZE // 1024} KB)."
                ),
            }

        # 4. Syntax validation (raises SyntaxValidationError on failure)
        try:
            validate_syntax(target, content)
        except SyntaxValidationError as exc:
            return {"ok": False, "reason": str(exc)}

        # 5. Atomic write
        try:
            atomic_write(target, content)
        except AtomicWriteError as exc:
            return {"ok": False, "reason": str(exc)}

        return {"ok": True, "path": str(target)}
