"""
Synchronous SQLite helper for file storage within Chainlit's DB.
Uses sqlite3 with WAL.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
# Point to the data/temp/chainlit.db
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "temp" / "chainlit.db"


class Database:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.conn: Optional[sqlite3.Connection] = None
        self.connect()

    def connect(self) -> None:
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        # Performance settings
        self.conn.execute("PRAGMA journal_mode = WAL;")
        self.conn.execute("PRAGMA synchronous = NORMAL;")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        assert self.conn
        try:
            schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
            self.conn.executescript(schema_sql)
            self.conn.commit()
        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                print("ℹ️ Database locked during schema check, skipping.")
            else:
                # If table already exists with different schema, this might not fail but won't migrate.
                # Assuming fresh start or compatible schema.
                raise e

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None

    def add_file(self, thread_id: str, path: str, ftype: str = "", summary: str = "") -> int:
        assert self.conn
        cursor = self.conn.execute(
            "INSERT INTO files (thread_id, path, type, summary) VALUES (?, ?, ?, ?)",
            (thread_id, path, ftype, summary),
        )
        self.conn.commit()
        return cursor.lastrowid
    
    def get_files(self, thread_id: str) -> list:
        assert self.conn
        cursor = self.conn.execute(
            "SELECT * FROM files WHERE thread_id = ?", (thread_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

def init_db_sync(db_path: Path | str = DEFAULT_DB_PATH) -> Database:
    return Database(db_path)