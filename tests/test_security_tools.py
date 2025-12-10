import tempfile
from pathlib import Path

import backend.tools  # noqa: F401
from backend.tools.python_exec import PythonExecTool
from backend.tools.shell_exec import ShellExecTool
from backend.tools.sql_query import SQLQueryTool
from backend.tools.file_loader import FileLoaderTool


def test_python_exec_blocks_import_and_dunder():
    tool = PythonExecTool()
    res = tool.run("import os")
    assert res["status"] == "error"
    res2 = tool.run("__import__('os')")
    assert res2["status"] == "error"


def test_shell_exec_blocks_chaining():
    tool = ShellExecTool()
    res = tool.run("dir && rm -rf /")
    assert res["status"] == "error"


def test_sql_query_readonly_blocks_non_select():
    tool = SQLQueryTool()
    res = tool.run("update users set name='x'", readonly=True)
    assert res["status"] == "error"


def test_file_loader_reads_temp_text():
    tool = FileLoaderTool()
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "sample.txt"
        p.write_text("hello world", encoding="utf-8")
        res = tool.run(str(p))
        assert res["status"] == "ok"
        assert "hello" in res["content"]
