import sqlite3

from backend.tools.sql_query import SQLQueryTool


def test_sql_query_blocks_non_select_when_readonly():
    tool = SQLQueryTool()
    res = tool.run("update users set name='x'", readonly=True)
    assert res["status"] == "error"


def test_sql_query_limits_rows(monkeypatch):
    tool = SQLQueryTool()
    sql = "select * from test"

    class DummyRow(dict):
        def __getattr__(self, item):
            return self[item]

    rows = [DummyRow({"a": i}) for i in range(tool.MAX_ROWS + 10)]

    def fake_connect(path):
        class Conn:
            def __init__(self):
                self.row_factory = None

            def execute(self, *_args, **_kwargs):
                class Cur:
                    def fetchall(self_inner):
                        return rows

                    def close(self_inner):
                        return None

                return Cur()

            def close(self):
                return None

        return Conn()

    monkeypatch.setattr(sqlite3, "connect", fake_connect)

    res = tool.run(sql, readonly=True)
    assert res["status"] == "ok"
    assert res["rowcount"] == len(rows)
    assert res["rowcount_returned"] == tool.MAX_ROWS
    assert len(res["rows"]) == tool.MAX_ROWS
