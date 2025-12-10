from backend.tools import TOOL_REGISTRY
from backend.tools.planning import PlanningTool
from backend.tools.shell_exec import ShellExecTool


def test_registry_contains_core_tools():
    for name in ["file_loader", "web_search", "python_exec", "sql_query", "image_analysis", "shell_exec", "planning"]:
        assert name in TOOL_REGISTRY


def test_planning_returns_plan():
    tool = PlanningTool()
    result = tool.run(goal="test goal")
    assert result["status"] == "ok"
    assert result["plan"]


def test_shell_exec_allowlist_blocks():
    tool = ShellExecTool()
    result = tool.run("rm -rf /", allowed=["echo"])
    assert result["status"] == "error"
