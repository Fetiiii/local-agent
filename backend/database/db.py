"""
Synchronous SQLite helper for conversation storage.
Uses sqlite3 with WAL and foreign keys enabled.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

SCHEMA_PATH = Path(__file__).with_name("schema.sql")
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "temp" / "chat.db"


class Database:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.conn: Optional[sqlite3.Connection] = None
        self.connect()

    def connect(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        
        # Performans ve kilitlenme karşıtı ayarlar
        self.conn.execute("PRAGMA foreign_keys = ON;")
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
                print("ℹ️ Database locked during schema check, skipping (already initialized).")
            else:
                raise e

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None

    def create_conversation(self, title: str = "New Chat", mode: str = "chat") -> int:
        assert self.conn
        cursor = self.conn.execute(
            "INSERT INTO conversations (title, mode) VALUES (?, ?)", (title, mode)
        )
        self.conn.commit()
        return cursor.lastrowid

    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        meta: Optional[Dict[str, Any]] = None,
    ) -> int:
        assert self.conn
        # guard: ensure conversation exists
        conv = self.get_conversation(conversation_id)
        if not conv:
            raise sqlite3.IntegrityError("conversation does not exist")
        cursor = self.conn.execute(
            "INSERT INTO messages (conversation_id, role, content, meta) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, json.dumps(meta or {})),
        )
        self.conn.commit()
        return cursor.lastrowid

    def get_messages(self, conversation_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        assert self.conn
        cursor = self.conn.execute(
            "SELECT id, role, content, meta, created_at FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
            (conversation_id, limit),
        )
        rows = cursor.fetchall()
        messages = []
        for row in rows:
            meta = json.loads(row["meta"]) if row["meta"] else {}
            messages.append(
                {
                    "id": row["id"],
                    "role": row["role"],
                    "content": row["content"],
                    "meta": meta,
                    "created_at": row["created_at"],
                }
            )
        return list(reversed(messages))

    def list_conversations(self, limit: int = 20) -> List[Dict[str, Any]]:
        assert self.conn
        cursor = self.conn.execute(
            "SELECT id, title, mode, created_at FROM conversations ORDER BY id DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        return [
            {"id": row["id"], "title": row["title"], "mode": row["mode"], "created_at": row["created_at"]}
            for row in rows
        ]

    def update_conversation_mode(self, conversation_id: int, mode: str) -> None:
        assert self.conn
        self.conn.execute("UPDATE conversations SET mode = ? WHERE id = ?", (mode, conversation_id))
        self.conn.commit()

    def get_conversation(self, conversation_id: int) -> Optional[Dict[str, Any]]:
        assert self.conn
        cursor = self.conn.execute(
            "SELECT id, title, mode, created_at FROM conversations WHERE id = ?", (conversation_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return {"id": row["id"], "title": row["title"], "mode": row["mode"], "created_at": row["created_at"]}

    def rename_conversation(self, conversation_id: int, title: str) -> None:
        assert self.conn
        self.conn.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conversation_id))
        self.conn.commit()

    def delete_conversation(self, conversation_id: int) -> None:
        assert self.conn
        self.conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        self.conn.commit()

    def add_file(self, conversation_id: int, path: str, ftype: str = "", summary: str = "") -> int:
        assert self.conn
        cursor = self.conn.execute(
            "INSERT INTO files (conversation_id, path, type, summary) VALUES (?, ?, ?, ?)",
            (conversation_id, path, ftype, summary),
        )
        self.conn.commit()
        return cursor.lastrowid


def init_db_sync(db_path: Path | str = DEFAULT_DB_PATH) -> Database:
    return Database(db_path)
