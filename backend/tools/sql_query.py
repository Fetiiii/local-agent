"""Execute SQL queries against configured SQLite DB (read-only by default)."""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

from backend.tools import BaseTool, register_tool


SAFE_PREFIXES = ("select", "pragma", "with")


class SQLQueryTool:
    name = "sql_query"
    description = "Run SQL queries on configured databases."
    MAX_ROWS = 200
    MAX_BYTES = 2_000_000  # guardrail for huge payloads

    def _is_safe(self, sql: str, readonly: bool) -> bool:
        cleaned = sql.strip().lower()
        if not readonly:
            return True
        return cleaned.startswith(SAFE_PREFIXES)

    def _limit_rows(self, rows: List[sqlite3.Row]) -> List[sqlite3.Row]:
        return rows[: self.MAX_ROWS]

    def run(self, query: str, **kwargs: Any) -> Dict[str, Any]:
        sql = (kwargs.get("query") or query or "").strip()
        db_path = kwargs.get("db_path") or "data/temp/chat.db"
        readonly = kwargs.get("readonly", True)
        if not sql:
            return {"status": "error", "message": "No query provided."}

        if not self._is_safe(sql, readonly):
            return {"status": "error", "message": "Only SELECT/PRAGMA/WITH queries allowed in readonly mode."}

        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cur = conn.execute(sql)
            rows = cur.fetchall()
            cur.close()
            conn.close()

            limited = self._limit_rows(rows)
            data = [dict(r) for r in limited]

            approx_bytes = sum(len(str(v)) for row in data for v in row.values())
            if approx_bytes > self.MAX_BYTES:
                data = data[:10]

            return {
                "status": "ok",
                "query": sql,
                "rows": data,
                "rowcount": len(rows),
                "rowcount_returned": len(data),
                "db_path": db_path,
                "readonly": bool(readonly),
            }
        except Exception as e:
            return {"status": "error", "query": sql, "message": str(e)}


register_tool(SQLQueryTool())
