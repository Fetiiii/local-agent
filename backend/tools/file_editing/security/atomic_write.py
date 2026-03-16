"""
backend/tools/file_editing/security/atomic_write.py
-----------------------------------------------------
Atomic file-write utility.

Safety guarantee
----------------
A crash or OS interruption during a plain open()+write() call can leave the
target file in a truncated / partially-written state.  This module prevents
that by writing to a sibling `.tmp` file first, flushing + fsyncing the OS
buffer to disk, and then atomically replacing the target via os.replace().

On POSIX   – os.replace() is guaranteed atomic (rename syscall).
On Windows – os.replace() is NOT atomic in the kernel sense but is still
             a single Win32 call (MoveFileExW with MOVEFILE_REPLACE_EXISTING),
             which is far safer than plain truncate+write because the target
             only disappears when the rename succeeds.
"""

import os
import tempfile
from pathlib import Path


class AtomicWriteError(OSError):
    """Raised when an atomic write operation fails."""


def atomic_write(target: Path, content: str, encoding: str = "utf-8") -> None:
    """
    Write *content* to *target* atomically.

    Steps
    -----
    1. Write content to a temporary file in the same directory as target.
    2. Flush the internal Python buffer and fsync the OS buffer.
    3. Atomically replace target with the temporary file.

    Parameters
    ----------
    target:   Absolute path to the destination file.
    content:  Text content to write.
    encoding: Character encoding (default UTF-8).

    Raises
    ------
    AtomicWriteError: if the write or replace fails.
    """
    target = Path(target)
    parent = target.parent

    # Ensure the parent directory exists before creating the temp file.
    parent.mkdir(parents=True, exist_ok=True)

    tmp_path: Path | None = None
    try:
        # Create a named temporary file in the same directory so that
        # os.replace() below is guaranteed to stay on the same filesystem
        # (cross-device rename would fail).
        fd, tmp_str = tempfile.mkstemp(
            suffix=".tmp",
            prefix=f"_{target.name}_",
            dir=str(parent),
        )
        tmp_path = Path(tmp_str)

        try:
            with os.fdopen(fd, "w", encoding=encoding) as fh:
                fh.write(content)
                fh.flush()
                # Force OS-level buffer flush so data is on disk before rename.
                os.fsync(fh.fileno())
        except Exception as exc:
            raise AtomicWriteError(
                f"Failed to write temporary file {tmp_path}: {exc}"
            ) from exc

        # Atomic rename: target either contains the old content or the new one,
        # never a half-written mix.
        try:
            os.replace(tmp_path, target)
        except Exception as exc:
            raise AtomicWriteError(
                f"Failed to atomically replace {target}: {exc}"
            ) from exc

    except AtomicWriteError:
        # Clean up the temp file if it still exists.
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise
