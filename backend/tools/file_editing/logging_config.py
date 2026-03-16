"""
backend/tools/file_editing/logging_config.py
---------------------------------------------
Shared logger for the entire file-editing subsystem.

All tool modules import `logger` from here to get a consistent,
timestamped file handler that writes to logs/agent_actions.log.
Format mirrors:  [HH:MM] <action>  <details>
"""

import logging
from pathlib import Path

from backend.tools.file_editing.config import LOG_FILE

# Ensure the log directory exists before the handler is created.
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

# ── Module-level logger ────────────────────────────────────────────────────────
logger: logging.Logger = logging.getLogger("file_editing")

if not logger.handlers:
    logger.setLevel(logging.INFO)

    # File handler — persists all tool actions
    _file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _file_handler.setLevel(logging.INFO)
    _file_handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M")
    )
    logger.addHandler(_file_handler)

    # Console handler — useful during development / debug sessions
    _console_handler = logging.StreamHandler()
    _console_handler.setLevel(logging.DEBUG)
    _console_handler.setFormatter(
        logging.Formatter("[file_editing] %(levelname)s: %(message)s")
    )
    logger.addHandler(_console_handler)

    # Prevent propagation to the root logger to avoid duplicate output
    logger.propagate = False
