"""
backend/tools/file_editing/file_reader.py
------------------------------------------
FileReaderTool — registered as "file_reader_v2".

Provides two capabilities:
  • list_tree(path)  — directory tree as text (ignores .git, __pycache__, node_modules)
  • read_lines(path, start_line, end_line) — numbered line viewport

Registered as "file_reader_v2" to avoid collision with the existing "file_loader" tool.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional

from backend.tools.file_editing.config import DATA_ROOT
from backend.tools.file_editing.logging_config import logger
from backend.tools.file_editing.security.path_resolver import SafePathResolver

# Directories the tree walk always skips.
_TREE_IGNORE = {".git", "__pycache__", "node_modules", ".mypy_cache", ".ruff_cache"}


class FileReaderTool:
    """
    Read files and directory trees safely inside DATA_ROOT.

    Tool name: ``file_reader_v2``

    run() dispatches on the ``action`` argument:
      - ``"list_tree"``  — returns a text tree of the directory.
      - ``"read_lines"`` — returns numbered lines (optionally sliced).
    """

    name = "file_reader_v2"
    description = (
        "Read files and list directory trees inside data/exports. "
        "Actions: 'list_tree' (path=optional) | 'read_lines' (path, start_line?, end_line?). "
        "read_lines returns lines in '1: content' format for viewport reading."
    )

    def __init__(self, root: Path | None = None) -> None:
        self._resolver = SafePathResolver(root or DATA_ROOT)

    # ── Public tool entry-point ────────────────────────────────────────────────

    def run(self, action: str = "list_tree", **kwargs: Any) -> Dict[str, Any]:
        """
        Dispatch to the requested action.

        Parameters
        ----------
        action: ``"list_tree"`` or ``"read_lines"``
        **kwargs: action-specific arguments forwarded verbatim.
        """
        if action == "list_tree":
            return self.list_tree(kwargs.get("path"))
        if action == "read_lines":
            return self.read_lines(
                path=kwargs["path"],
                start_line=kwargs.get("start_line"),
                end_line=kwargs.get("end_line"),
            )
        return {"text": f"❌ Unknown action '{action}'. Use 'list_tree' or 'read_lines'."}

    # ── list_tree ──────────────────────────────────────────────────────────────

    def list_tree(self, path: Optional[str | Path] = None) -> Dict[str, Any]:
        """
        Return the directory tree rooted at *path* (default: DATA_ROOT) as text.

        Skips .git, __pycache__, node_modules and friends so the output stays
        readable for an LLM context window.

        Parameters
        ----------
        path: Relative or absolute path inside DATA_ROOT.
              Defaults to DATA_ROOT itself.

        Returns
        -------
        Dict with keys ``text`` (the tree) and ``root`` (resolved root path).
        """
        try:
            if path:
                root = self._resolver.resolve(path)
            else:
                root = self._resolver.root

            if not root.exists():
                return {"text": f"❌ Path does not exist: {root}"}
            if not root.is_dir():
                return {"text": f"❌ Path is not a directory: {root}"}

            lines: list[str] = [str(root)]
            self._walk_tree(root, prefix="", lines=lines)
            tree_text = "\n".join(lines)

            logger.info("list_tree %s", root)
            return {"text": tree_text, "root": str(root)}

        except Exception as exc:
            logger.error("list_tree failed: %s", exc)
            return {"text": f"❌ list_tree error: {exc}"}

    def _walk_tree(self, directory: Path, prefix: str, lines: list[str]) -> None:
        """Recursive helper — builds a Unicode tree view."""
        try:
            entries = sorted(
                [e for e in directory.iterdir() if e.name not in _TREE_IGNORE],
                key=lambda e: (e.is_file(), e.name.lower()),
            )
        except PermissionError:
            lines.append(f"{prefix}└── [permission denied]")
            return

        for idx, entry in enumerate(entries):
            connector = "└── " if idx == len(entries) - 1 else "├── "
            lines.append(f"{prefix}{connector}{entry.name}{'/' if entry.is_dir() else ''}")
            if entry.is_dir():
                extension = "    " if idx == len(entries) - 1 else "│   "
                self._walk_tree(entry, prefix + extension, lines)

    # ── read_lines ─────────────────────────────────────────────────────────────

    def read_lines(
        self,
        path: str | Path,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Return numbered lines from a file, optionally sliced to a viewport.

        Lines are 1-indexed in both the arguments and the output, matching
        editor conventions so the LLM can reference them directly.

        Output format::

            1: first line content
            2: second line content

        Parameters
        ----------
        path:       Path to the file (relative to DATA_ROOT or absolute inside it).
        start_line: First line to include (1-indexed, default: 1).
        end_line:   Last line to include (1-indexed, inclusive, default: EOF).

        Returns
        -------
        Dict with ``text`` (numbered lines), ``total_lines``, and ``path``.
        """
        try:
            resolved = self._resolver.resolve(path)

            if not resolved.exists():
                return {"text": f"❌ File not found: {path}"}
            if not resolved.is_file():
                return {"text": f"❌ Path is a directory: {path}"}

            raw_lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
            total = len(raw_lines)

            # Normalise viewport bounds (convert to 0-indexed slice internally).
            start = max(1, int(start_line)) if start_line is not None else 1
            end = min(total, int(end_line)) if end_line is not None else total

            if start > total:
                return {
                    "text": f"❌ start_line {start} exceeds file length ({total} lines).",
                    "total_lines": total,
                    "path": str(resolved),
                }

            numbered = "\n".join(
                f"{i + 1}: {raw_lines[i]}" for i in range(start - 1, end)
            )

            logger.info("read_lines %s %d-%d", resolved.name, start, end)
            return {
                "text": numbered,
                "total_lines": total,
                "shown_lines": f"{start}-{end}",
                "path": str(resolved),
            }

        except Exception as exc:
            logger.error("read_lines failed: %s", exc)
            return {"text": f"❌ read_lines error: {exc}"}
