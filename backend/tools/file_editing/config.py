"""
backend/tools/file_editing/config.py
-------------------------------------
Central constants for the file-editing subsystem.

Values are derived from backend.core.settings (Pydantic BaseSettings)
so they can be overridden via environment variables without touching code.
"""

from pathlib import Path
from backend.core.settings import settings

# ── Root directory for all file I/O ───────────────────────────────────────────
DATA_ROOT: Path = Path(
    getattr(settings, "file_edit_data_root", "data/exports")
).resolve()

# ── Limits ────────────────────────────────────────────────────────────────────
MAX_FILE_SIZE: int = int(
    getattr(settings, "file_edit_max_file_size", 204_800)
)  # 200 KB

MAX_FILES_PER_CALL: int = int(
    getattr(settings, "file_edit_max_files_per_call", 20)
)

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE: Path = Path("logs/agent_actions.log")
