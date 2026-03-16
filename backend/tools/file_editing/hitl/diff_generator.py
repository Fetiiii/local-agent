"""
backend/tools/file_editing/hitl/diff_generator.py
---------------------------------------------------
Generate unified (git-style) diffs using ``difflib``.

Provides a single public function ``generate_diff()`` that both
the approval manager and the demo script use to show what would
change before a write is committed.
"""

from __future__ import annotations

import difflib
from typing import Sequence


def generate_diff(
    old: str,
    new: str,
    filename: str = "file",
    context_lines: int = 3,
) -> str:
    """
    Return a unified diff string suitable for display in a terminal or UI.

    Output format mirrors ``git diff``::

        --- old/config.py
        +++ new/config.py
        @@ -12,7 +12,7 @@
         unchanged line
        -old line
        +new line
         unchanged line

    Parameters
    ----------
    old:           Original file content.
    new:           New file content after proposed change.
    filename:      Logical filename used in the diff header lines.
    context_lines: Number of unchanged context lines to show around each hunk.

    Returns
    -------
    str: Unified diff text, or empty string if old == new.
    """
    if old == new:
        return ""

    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)

    diff_lines: Sequence[str] = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"--- old/{filename}",
            tofile=f"+++ new/{filename}",
            n=context_lines,
        )
    )

    return "".join(diff_lines)


def has_changes(old: str, new: str) -> bool:
    """Return True if *old* and *new* differ at all."""
    return old != new
