"""
backend/tools/file_editing/context_manager.py
----------------------------------------------
FileContextManager — utilities that help the LLM stay within its context
window when working with large files.

Three helpers are provided:

  chunk_file(path, chunk_size)  — infinite iterator over numbered text chunks
  preview(path, max_lines)      — head + tail excerpt with line count summary
  summarize(path)               — first docstring / comment block + structure
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Generator, Optional

from backend.tools.file_editing.config import DATA_ROOT
from backend.tools.file_editing.logging_config import logger
from backend.tools.file_editing.security.path_resolver import SafePathResolver

# Default chunk and preview sizes (in lines).
_DEFAULT_CHUNK_LINES = 80
_DEFAULT_PREVIEW_HEAD = 20
_DEFAULT_PREVIEW_TAIL = 10


class FileContextManager:
    """
    Reduce LLM context load when dealing with large files.

    Parameters
    ----------
    root: Effective root for SafePathResolver (defaults to DATA_ROOT).
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        self._resolver = SafePathResolver(root or DATA_ROOT)

    # ── chunk_file ─────────────────────────────────────────────────────────────

    def chunk_file(
        self,
        path: str | Path,
        chunk_size: int = _DEFAULT_CHUNK_LINES,
    ) -> Generator[str, None, None]:
        """
        Yield the file's content in consecutive numbered chunks.

        Each yielded string is a block of *chunk_size* lines prefixed with a
        header like ``[Chunk 1/12 — lines 1-80]`` so the LLM can reference
        position without needing the full text at once.

        Parameters
        ----------
        path:       File path (relative to DATA_ROOT or absolute inside it).
        chunk_size: Number of lines per chunk (default 80).

        Yields
        ------
        str: One chunk at a time, ready to be sent to the LLM as a message.
        """
        resolved = self._resolver.resolve(path)
        if not resolved.is_file():
            yield f"❌ File not found or not a file: {path}"
            return

        all_lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
        total_lines = len(all_lines)
        total_chunks = max(1, -(-total_lines // chunk_size))  # ceiling division

        for chunk_idx in range(total_chunks):
            start = chunk_idx * chunk_size
            end = min(start + chunk_size, total_lines)
            numbered = "\n".join(
                f"{i + 1}: {all_lines[i]}" for i in range(start, end)
            )
            header = (
                f"[Chunk {chunk_idx + 1}/{total_chunks} — "
                f"lines {start + 1}-{end} of {total_lines}]"
            )
            logger.info("chunk_file %s chunk %d/%d", resolved.name, chunk_idx + 1, total_chunks)
            yield f"{header}\n{numbered}"

    # ── preview ────────────────────────────────────────────────────────────────

    def preview(
        self,
        path: str | Path,
        head_lines: int = _DEFAULT_PREVIEW_HEAD,
        tail_lines: int = _DEFAULT_PREVIEW_TAIL,
    ) -> str:
        """
        Return a compact head + tail excerpt of a file.

        Useful for quickly understanding a file without loading every line.
        If the file is short enough to show in full, no truncation occurs.

        Parameters
        ----------
        path:       File path.
        head_lines: Number of lines to show from the start.
        tail_lines: Number of lines to show from the end.

        Returns
        -------
        str: The excerpt including a separator line if truncated.
        """
        resolved = self._resolver.resolve(path)
        if not resolved.is_file():
            return f"❌ File not found: {path}"

        lines = resolved.read_text(encoding="utf-8", errors="replace").splitlines()
        total = len(lines)

        if total <= head_lines + tail_lines + 1:
            # File is short; return it all with line numbers.
            return "\n".join(f"{i + 1}: {line}" for i, line in enumerate(lines))

        head = "\n".join(f"{i + 1}: {lines[i]}" for i in range(head_lines))
        omitted = total - head_lines - tail_lines
        separator = f"\n... [{omitted} lines omitted] ...\n"
        tail_start = total - tail_lines
        tail = "\n".join(f"{i + 1}: {lines[i]}" for i in range(tail_start, total))

        logger.info("preview %s (total=%d)", resolved.name, total)
        return head + separator + tail

    # ── summarize ──────────────────────────────────────────────────────────────

    def summarize(self, path: str | Path) -> str:
        """
        Return a structural summary of a file.

        For Python files this extracts module docstring + top-level symbols
        (classes, functions, imports) using ``ast``.

        For other file types it returns the first non-empty comment block /
        docstring found via simple regex, plus a line count.

        Parameters
        ----------
        path: File path.

        Returns
        -------
        str: A compact textual summary appropriate for LLM context.
        """
        resolved = self._resolver.resolve(path)
        if not resolved.is_file():
            return f"❌ File not found: {path}"

        content = resolved.read_text(encoding="utf-8", errors="replace")
        ext = resolved.suffix.lower()

        if ext == ".py":
            return self._summarize_python(resolved.name, content)
        return self._summarize_generic(resolved.name, content)

    # ── Internal helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _summarize_python(filename: str, content: str) -> str:
        """Extract module docstring + top-level symbol names from Python source."""
        lines = content.splitlines()
        total = len(lines)

        try:
            tree = ast.parse(content)
        except SyntaxError as exc:
            return (
                f"📄 {filename} — {total} lines | ⚠️ SyntaxError: {exc.msg} "
                f"(line {exc.lineno})\n"
                + "\n".join(lines[:10])
            )

        # Module docstring
        docstring = ast.get_docstring(tree) or "(no module docstring)"
        # First 3 lines of the docstring to keep it brief
        doc_preview = "\n".join(docstring.splitlines()[:3])

        # Top-level symbols
        symbols = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(f"  def {node.name}()")
            elif isinstance(node, ast.ClassDef):
                methods = [
                    m.name
                    for m in ast.iter_child_nodes(node)
                    if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                methods_str = ", ".join(methods[:5])
                if len(methods) > 5:
                    methods_str += f", +{len(methods) - 5} more"
                symbols.append(f"  class {node.name}  [{methods_str}]")
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [
                    alias.asname or alias.name for alias in node.names
                ]
                symbols.append(f"  import {', '.join(names)}")

        symbols_str = "\n".join(symbols) if symbols else "  (no top-level symbols)"
        return (
            f"📄 {filename} — {total} lines\n"
            f"Docstring: {doc_preview}\n"
            f"Structure:\n{symbols_str}"
        )

    @staticmethod
    def _summarize_generic(filename: str, content: str) -> str:
        """Return the first comment block + line count for non-Python files."""
        lines = content.splitlines()
        total = len(lines)

        # Collect leading comment/docstring lines (lines starting with #, //, * etc.)
        comment_lines = []
        for line in lines[:30]:
            stripped = line.strip()
            if stripped.startswith(("#", "//", "*", "/*", '"""', "'''")):
                comment_lines.append(stripped)
            elif comment_lines:
                break  # stop at first non-comment line after we started collecting

        header = "\n".join(comment_lines[:10]) or "(no leading comments)"
        return f"📄 {filename} — {total} lines\nHeader:\n{header}"
