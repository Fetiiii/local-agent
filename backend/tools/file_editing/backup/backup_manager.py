"""
backend/tools/file_editing/backup/backup_manager.py
----------------------------------------------------
BackupManager — save previous file versions before any approved modification.

Backup layout::

    data/temp/backups/
    └── 20260315_190512_abc123/
        ├── metadata.json
        └── files/
            └── my_script.py   ← copy of the original content

The timestamp + a 6-char random hex suffix gives unique, collision-free IDs
even when multiple backups are created within the same second.

Restoring a backup copies the saved files back to their original paths
(subject to SafePathResolver confinement), replacing whatever is there now.
"""

from __future__ import annotations

import json
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.tools.file_editing.logging_config import logger
from backend.tools.file_editing.security.atomic_write import atomic_write
from backend.tools.file_editing.security.path_resolver import SafePathResolver, PathTraversalError
from backend.tools.file_editing.config import DATA_ROOT

# Root directory for all backups.
_BACKUP_ROOT = Path("data/temp/backups")


class BackupError(RuntimeError):
    """Raised when a backup or restore operation fails."""


class BackupManager:
    """
    Create and restore file backups before agent edits.

    Parameters
    ----------
    backup_root: Directory that stores all backup snapshots.
                 Defaults to ``data/temp/backups``.
    data_root:   SafePathResolver root (DATA_ROOT by default).
                 Used to confine restore targets.
    """

    def __init__(
        self,
        backup_root: Optional[Path] = None,
        data_root: Optional[Path] = None,
    ) -> None:
        self._backup_root = (backup_root or _BACKUP_ROOT).resolve()
        self._backup_root.mkdir(parents=True, exist_ok=True)
        self._resolver = SafePathResolver(data_root or DATA_ROOT)

    # ── Public API ─────────────────────────────────────────────────────────────

    def create_backup(
        self,
        file_paths: List[Path | str],
        action: str = "agent edit",
    ) -> str:
        """
        Save the current content of *file_paths* into a new timestamped snapshot.

        Parameters
        ----------
        file_paths: Absolute paths of the files to back up.
        action:     Human-readable description stored in metadata.json.

        Returns
        -------
        str: The backup ID (directory name), e.g. ``"20260315_190512_a3f9c1"``.

        Raises
        ------
        BackupError: if any file cannot be read.
        """
        backup_id = self._make_id()
        snapshot_dir = self._backup_root / backup_id
        files_dir = snapshot_dir / "files"
        files_dir.mkdir(parents=True, exist_ok=True)

        backed_up: List[str] = []
        for raw_path in file_paths:
            src = Path(raw_path)
            if not src.exists():
                logger.warning("backup skip (not found): %s", src)
                continue
            # Store each file with a safe flat name — use the stem + a hash if
            # multiple files share the same name.
            dest = files_dir / src.name
            try:
                shutil.copy2(src, dest)
                backed_up.append(str(src))
            except OSError as exc:
                raise BackupError(f"Cannot backup {src}: {exc}") from exc

        # Write metadata sidecar.
        metadata: Dict[str, Any] = {
            "time": datetime.now(tz=timezone.utc).isoformat(),
            "backup_id": backup_id,
            "files": backed_up,
            "action": action,
        }
        meta_path = snapshot_dir / "metadata.json"
        try:
            atomic_write(meta_path, json.dumps(metadata, indent=2))
        except Exception as exc:
            raise BackupError(f"Cannot write metadata: {exc}") from exc

        logger.info(
            "backup created %s — %d file(s) for '%s'",
            backup_id,
            len(backed_up),
            action,
        )
        return backup_id

    def restore_backup(self, backup_id: str) -> Dict[str, Any]:
        """
        Restore files from backup *backup_id* to their original paths.

        The original paths are read from ``metadata.json`` and the saved copies
        are written back atomically.

        Parameters
        ----------
        backup_id: ID returned by a previous ``create_backup()`` call.

        Returns
        -------
        Dict with ``restored`` (list of paths) and ``errors`` (list of messages).
        """
        snapshot_dir = self._backup_root / backup_id
        if not snapshot_dir.exists():
            return {
                "text": f"❌ Backup '{backup_id}' not found.",
                "restored": [],
                "errors": [],
            }

        meta_path = snapshot_dir / "metadata.json"
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {
                "text": f"❌ Cannot read backup metadata: {exc}",
                "restored": [],
                "errors": [],
            }

        files_dir = snapshot_dir / "files"
        restored: List[str] = []
        errors: List[str] = []

        for original_path_str in metadata.get("files", []):
            original_path = Path(original_path_str)
            saved_copy = files_dir / original_path.name

            if not saved_copy.exists():
                errors.append(f"Saved copy not found: {saved_copy.name}")
                continue

            try:
                content = saved_copy.read_text(encoding="utf-8", errors="replace")
                atomic_write(original_path, content)
                restored.append(original_path_str)
                logger.info("restore %s from backup %s", original_path.name, backup_id)
            except Exception as exc:
                errors.append(f"{original_path.name}: {exc}")

        summary = f"✅ Restored {len(restored)} file(s) from backup '{backup_id}'."
        if errors:
            summary += f" ⚠️ {len(errors)} error(s)."

        return {"text": summary, "restored": restored, "errors": errors}

    def list_backups(self) -> List[Dict[str, Any]]:
        """
        Return a list of all backup snapshots, newest first.

        Each entry contains: ``backup_id``, ``time``, ``action``, ``files``.
        """
        snapshots = []
        for d in sorted(self._backup_root.iterdir(), reverse=True):
            if not d.is_dir():
                continue
            meta_path = d / "metadata.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                    snapshots.append(meta)
                except Exception:
                    snapshots.append({"backup_id": d.name, "error": "unreadable metadata"})
        return snapshots

    def get_backup_info(self, backup_id: str) -> Optional[Dict[str, Any]]:
        """Return metadata for a specific backup ID, or None if not found."""
        meta_path = self._backup_root / backup_id / "metadata.json"
        if not meta_path.exists():
            return None
        try:
            return json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            return None

    # ── Internal helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _make_id() -> str:
        """Generate a unique backup ID: ``YYYYMMDD_HHMMSS_<6hex>``."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        rand = secrets.token_hex(3)  # 6 hex chars
        return f"{ts}_{rand}"
