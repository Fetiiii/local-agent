import subprocess

from backend.tools.shell_exec import ShellExecTool


def test_shell_exec_blocks_forbidden_keywords():
    tool = ShellExecTool()
    res = tool.run("rm -rf /", allowed=["rm"])
    assert res["status"] == "error"


def test_shell_exec_allows_allowlisted(monkeypatch):
    tool = ShellExecTool()
    calls = {}

    def fake_run(cmd, **kwargs):
        calls["cmd"] = cmd
        return subprocess.CompletedProcess(cmd, 0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    res = tool.run("echo hello", allowed=["echo "])
    assert res["status"] == "ok"
    assert calls["cmd"] == "echo hello"
    assert res["stdout"] == "ok"
