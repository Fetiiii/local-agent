"""
backend/tools/file_editing/file_surgeon.py
-------------------------------------------
FileSurgeonTool — registered as "file_surgeon".

Edits an existing file by locating a ``search_block`` and replacing it with
a ``replace_block``.  Uses a three-tier matching strategy:

  Tier 1 — Exact match               : fast, preferred
  Tier 2 — Normalised-whitespace     : tolerates indent drift / CRLF vs LF
  Tier 3 — Fuzzy match (difflib)     : catches minor typos / extra blank lines

If multiple matches are found → raises an unambiguous error.
If no match is found → returns a diagnostic with the closest-matching region.

Safety
------
• Path is resolved through SafePathResolver (DATA_ROOT confinement).
• File is only written on a successful unique match.
• Write goes through atomic_write to prevent partial edits.
• Syntax is validated after constructing the new content.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.tools.file_editing.config import DATA_ROOT
from backend.tools.file_editing.logging_config import logger
from backend.tools.file_editing.security.atomic_write import atomic_write, AtomicWriteError
from backend.tools.file_editing.security.path_resolver import SafePathResolver, PathTraversalError
from backend.tools.file_editing.security.syntax_validator import validate_syntax, SyntaxValidationError

# Minimum similarity ratio for a fuzzy match to be considered a candidate.
_FUZZY_THRESHOLD = 0.75


class FileSurgeonTool:
    """
    Locate a text block inside a file and replace it.

    Tool name: ``file_surgeon``

    run() arguments
    ---------------
    path          : str   — file path (relative to DATA_ROOT)
    search_block  : str   — block of text to find
    replace_block : str   — replacement text
    """

    name = "file_surgeon"
    description = (
        "Edit an existing file by finding search_block and replacing it with replace_block. "
        "Uses exact → whitespace-tolerant → fuzzy matching. "
        "Raises an error on ambiguous (multiple) matches. "
        "Returns a diagnostic with closest matches when the block is not found."
    )

    def __init__(self, root: Optional[Path] = None) -> None:
        self._resolver = SafePathResolver(root or DATA_ROOT)

    # ── Public tool entry-point ────────────────────────────────────────────────

    def run(
        self,
        path: str,
        search_block: str,
        replace_block: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Find *search_block* in *path* and replace with *replace_block*.

        Returns
        -------
        Dict with ``text`` (status message) and optional ``diff`` preview.
        """
        # ── Resolve path ───────────────────────────────────────────────────────
        try:
            target = self._resolver.resolve(path)
        except PathTraversalError as exc:
            return {"text": f"❌ Path error: {exc}"}

        if not target.exists():
            return {"text": f"❌ File not found: {path}"}
        if not target.is_file():
            return {"text": f"❌ Path is not a file: {path}"}

        # ── Read original content ──────────────────────────────────────────────
        try:
            original = target.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            return {"text": f"❌ Cannot read file: {exc}"}

        # ── Attempt matching ───────────────────────────────────────────────────
        match_result = self._find_match(original, search_block)

        if match_result["status"] == "multiple":
            return {
                "text": (
                    f"❌ Ambiguous: search_block matched at {match_result['count']} locations "
                    f"using {match_result['tier']} matching. Narrow down the search_block "
                    f"to a unique passage and retry."
                )
            }

        if match_result["status"] == "none":
            diagnostic = self._build_diagnostic(original, search_block)
            return {
                "text": (
                    "❌ search_block not found in file. No changes made.\n\n"
                    f"**Closest region (similarity {diagnostic['score']:.0%}):**\n"
                    f"```\n{diagnostic['snippet']}\n```\n\n"
                    "Tip: Copy the exact text from the file into search_block."
                ),
                "closest_score": diagnostic["score"],
            }

        # Unique match found — perform the replacement.
        start, end = match_result["span"]  # character offsets in `original`
        new_content = original[:start] + replace_block + original[end:]

        # ── Post-edit syntax validation ────────────────────────────────────────
        try:
            validate_syntax(target, new_content)
        except SyntaxValidationError as exc:
            return {
                "text": (
                    f"❌ Replacement would produce invalid syntax: {exc}\n"
                    "No changes were written."
                )
            }

        # ── Atomic write ───────────────────────────────────────────────────────
        try:
            atomic_write(target, new_content)
        except AtomicWriteError as exc:
            return {"text": f"❌ Write failed: {exc}"}

        logger.info(
            "file_surgeon replace %s (tier=%s)",
            target.name,
            match_result["tier"],
        )
        return {
            "text": (
                f"✅ Replacement applied to {target.name} "
                f"(match tier: {match_result['tier']})."
            ),
            "tier": match_result["tier"],
            "path": str(target),
        }

    # ── Matching engine ────────────────────────────────────────────────────────

    def _find_match(
        self, content: str, search_block: str
    ) -> Dict[str, Any]:
        """
        Try each matching tier in order.  Return the first tier that yields
        exactly one match. Report "multiple" immediately if any tier has > 1.
        """

        # Tier 1: Exact string match
        exact_spans = _find_exact(content, search_block)
        if len(exact_spans) == 1:
            return {"status": "found", "tier": "exact", "span": exact_spans[0]}
        if len(exact_spans) > 1:
            return {"status": "multiple", "tier": "exact", "count": len(exact_spans)}

        # Tier 2: Normalised-whitespace match
        norm_spans = _find_normalised(content, search_block)
        if len(norm_spans) == 1:
            return {"status": "found", "tier": "normalised-whitespace", "span": norm_spans[0]}
        if len(norm_spans) > 1:
            return {
                "status": "multiple",
                "tier": "normalised-whitespace",
                "count": len(norm_spans),
            }

        # Tier 3: Fuzzy match
        fuzzy_result = _find_fuzzy(content, search_block)
        if fuzzy_result and fuzzy_result["score"] >= _FUZZY_THRESHOLD:
            if fuzzy_result["count"] == 1:
                return {
                    "status": "found",
                    "tier": f"fuzzy ({fuzzy_result['score']:.0%})",
                    "span": fuzzy_result["span"],
                }
            return {
                "status": "multiple",
                "tier": "fuzzy",
                "count": fuzzy_result["count"],
            }

        return {"status": "none"}

    def _build_diagnostic(
        self, content: str, search_block: str
    ) -> Dict[str, Any]:
        """Return the region of the file most similar to search_block."""
        search_lines = search_block.splitlines()
        content_lines = content.splitlines()
        n = len(search_lines)

        best_score = 0.0
        best_snippet = ""

        for i in range(max(1, len(content_lines) - n + 1)):
            window = content_lines[i : i + n]
            score = difflib.SequenceMatcher(
                None, search_lines, window
            ).ratio()
            if score > best_score:
                best_score = score
                best_snippet = "\n".join(window)

        return {"score": best_score, "snippet": best_snippet}


# ── Matching helpers ───────────────────────────────────────────────────────────

def _find_exact(content: str, search_block: str) -> List[Tuple[int, int]]:
    """Return list of (start, end) character spans for exact occurrences."""
    spans: List[Tuple[int, int]] = []
    start = 0
    while True:
        idx = content.find(search_block, start)
        if idx == -1:
            break
        spans.append((idx, idx + len(search_block)))
        start = idx + 1
    return spans


def _normalise(text: str) -> str:
    """Collapse all whitespace sequences (including newlines) to single space."""
    return re.sub(r"\s+", " ", text).strip()


def _find_normalised(content: str, search_block: str) -> List[Tuple[int, int]]:
    """
    Split both content and search_block into lines, normalise each line's
    whitespace, and look for the search pattern as a sub-sequence of lines.
    Returns character-level spans in the original content.
    """
    search_lines = [_normalise(l) for l in search_block.splitlines() if l.strip()]
    content_lines_raw = content.splitlines(keepends=True)
    content_lines_norm = [_normalise(l) for l in content_lines_raw]

    n = len(search_lines)
    if n == 0:
        return []

    spans: List[Tuple[int, int]] = []
    for i in range(len(content_lines_norm) - n + 1):
        if content_lines_norm[i : i + n] == search_lines:
            # Reconstruct char-level span from raw lines.
            char_start = sum(len(l) for l in content_lines_raw[:i])
            # Use all preceding matched lines at full length (incl. \n),
            # but strip the trailing line terminator off the LAST matched
            # line so that replace_block does not need to supply it and the
            # newline is preserved naturally in original[char_end:].
            last_raw = content_lines_raw[i + n - 1]
            inner_len = sum(len(l) for l in content_lines_raw[i : i + n - 1])
            char_end = char_start + inner_len + len(last_raw.rstrip("\r\n"))
            spans.append((char_start, char_end))
    return spans


def _find_fuzzy(
    content: str, search_block: str
) -> Optional[Dict[str, Any]]:
    """
    Slide a window of len(search_block lines) across the file and return the
    best-scoring match above _FUZZY_THRESHOLD, or None.
    """
    search_lines = search_block.splitlines()
    content_lines_raw = content.splitlines(keepends=True)
    n = len(search_lines)
    if n == 0 or n > len(content_lines_raw):
        return None

    best_score = 0.0
    best_i = -1
    candidates: List[int] = []

    for i in range(len(content_lines_raw) - n + 1):
        window = [l.rstrip("\n\r") for l in content_lines_raw[i : i + n]]
        score = difflib.SequenceMatcher(None, search_lines, window).ratio()
        if score > _FUZZY_THRESHOLD:
            if score > best_score:
                best_score = score
                best_i = i
                # Reset candidates list when a better score is found.
                candidates = [i]
            elif score == best_score:
                candidates.append(i)

    if best_i == -1:
        return None

    char_start = sum(len(l) for l in content_lines_raw[:best_i])
    # Same trailing-newline fix as _find_normalised: don't consume the \n
    # at the end of the last matched line so replace_block stays independent
    # of line terminator style.
    last_raw = content_lines_raw[best_i + n - 1]
    inner_len = sum(len(l) for l in content_lines_raw[best_i : best_i + n - 1])
    char_end = char_start + inner_len + len(last_raw.rstrip("\r\n"))

    return {
        "score": best_score,
        "span": (char_start, char_end),
        "count": len(candidates),
    }
