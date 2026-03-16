"""
backend/tools/file_editing/security/path_resolver.py
------------------------------------------------------
SafePathResolver — enforces that all file operations stay inside a
designated root directory (data/exports by default).

Security rationale
------------------
Without path confinement an LLM could construct arguments like
  ../../secrets.env
or an absolute path like
  C:/Windows/System32/anything
and the tool would happily read or overwrite those files.

pathlib.Path.resolve() normalises symlinks and `..` components, giving us
the canonical absolute path.  relative_to() then asserts that the resolved
path is a descendant of `root`; it raises ValueError if not.
"""

from pathlib import Path

from backend.tools.file_editing.config import DATA_ROOT


class PathTraversalError(PermissionError):
    """Raised when a requested path escapes the allowed root directory."""


class SafePathResolver:
    """
    Resolve file paths and enforce containment inside *root*.

    Parameters
    ----------
    root: Absolute base directory. Defaults to DATA_ROOT from config.
          All resolved paths must be descendants of this directory.

    Usage
    -----
    >>> resolver = SafePathResolver()
    >>> safe = resolver.resolve("reports/output.json")   # OK
    >>> resolver.resolve("../../etc/passwd")             # raises PathTraversalError
    """

    def __init__(self, root: Path | str | None = None) -> None:
        self.root: Path = Path(root).resolve() if root else DATA_ROOT.resolve()
        # Ensure the root exists so resolve() works correctly.
        self.root.mkdir(parents=True, exist_ok=True)

    # ── Public API ─────────────────────────────────────────────────────────────

    def resolve(self, path: str | Path) -> Path:
        """
        Return the absolute, normalised path for *path*.

        The result is always a descendant of ``self.root``.

        Parameters
        ----------
        path: Relative or absolute path to resolve.

        Returns
        -------
        Path: Resolved absolute path inside self.root.

        Raises
        ------
        PathTraversalError: if the resolved path escapes self.root.
        """
        p = Path(path)

        # If the caller supplied an absolute path, resolve it directly;
        # otherwise join it to root first (relative paths are the common case).
        if p.is_absolute():
            resolved = p.resolve()
        else:
            # Strip any leading slashes from the relative path to prevent
            # rooting it to the filesystem root when joined.
            resolved = (self.root / str(p).lstrip("/\\")).resolve()

        # The key safety check — relative_to() raises ValueError when resolved
        # is NOT a descendant of self.root.
        try:
            resolved.relative_to(self.root)
        except ValueError:
            raise PathTraversalError(
                f"Path '{path}' resolves to '{resolved}' which is outside the "
                f"allowed root '{self.root}'. Directory traversal is not permitted."
            )

        return resolved

    def is_safe(self, path: str | Path) -> bool:
        """
        Return True if *path* resolves safely within self.root, False otherwise.
        Never raises.
        """
        try:
            self.resolve(path)
            return True
        except (PathTraversalError, Exception):
            return False

    def relative(self, path: str | Path) -> Path:
        """
        Return the portion of *path* that is relative to self.root.
        Raises PathTraversalError if the path escapes root.
        """
        resolved = self.resolve(path)
        return resolved.relative_to(self.root)


# ── Module-level default resolver (uses DATA_ROOT) ────────────────────────────
default_resolver = SafePathResolver()
