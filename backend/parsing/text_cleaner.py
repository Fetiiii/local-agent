from __future__ import annotations

import re

CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b-\x1f]+")
MULTI_SPACE = re.compile(r"\s+")
BRACKET_TAG = re.compile(r"<\|.*?\|>")


def strip_control_chars(text: str) -> str:
    """Remove ASCII control characters that can leak from some parsers/LLMs."""
    return CONTROL_CHARS.sub("", text or "")


def collapse_blank_lines(text: str, max_consecutive: int = 2) -> str:
    """
    Collapse runs of blank lines to a maximum length.
    Useful for PDF/Word text that often has excessive spacing.
    """
    if max_consecutive < 1:
        max_consecutive = 1
    pattern = re.compile(r"(?:\n\s*){%d,}" % (max_consecutive + 1))
    return pattern.sub("\n" * max_consecutive, text)


def normalize_whitespace(text: str) -> str:
    """
    Collapse multiple whitespace characters into single spaces and trim.
    Keeps line breaks intact before collapsing blank lines.
    """
    if not text:
        return ""
    # Preserve intentional newlines first, then collapse spaces on each line
    text = strip_control_chars(text.replace("\r", ""))
    lines = []
    for line in text.split("\n"):
        line = BRACKET_TAG.sub("", line)
        lines.append(MULTI_SPACE.sub(" ", line).strip())
    collapsed = "\n".join(lines)
    return collapse_blank_lines(collapsed).strip()


def clean_text(text: str, keep_newlines: bool = True) -> str:
    """
    End-to-end cleaner:
    - strip control chars and llama-like tags
    - normalize whitespace
    - optionally keep single newlines
    """
    if not text:
        return ""
    cleaned = strip_control_chars(text.replace("\r", ""))
    cleaned = BRACKET_TAG.sub("", cleaned)
    if not keep_newlines:
        cleaned = MULTI_SPACE.sub(" ", cleaned)
        return cleaned.strip()
    return normalize_whitespace(cleaned)


def excerpt(text: str, max_chars: int = 400) -> str:
    """Return a safe preview shortened to max_chars."""
    trimmed = clean_text(text)
    if max_chars <= 0:
        return ""
    if len(trimmed) < max_chars:
        return trimmed
    if max_chars <= 3:
        return trimmed[:max_chars]
    return trimmed[: max_chars - 3].rstrip() + "..."
