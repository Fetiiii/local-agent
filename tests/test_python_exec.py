from backend.tools.python_exec import PythonExecTool


def test_python_exec_blocks_imports_and_attrs():
    tool = PythonExecTool()
    res = tool.run("import os")
    assert res["status"] == "error"
    res_attr = tool.run("x = (1).real")
    assert res_attr["status"] == "error"


def test_python_exec_runs_simple_code():
    tool = PythonExecTool()
    res = tool.run("x = 2 + 3\nprint(x)")
    assert res["status"] == "ok"
    assert res["locals"]["x"] == 5
    assert "5" in res["output"]
