"""Run shell commands with an allowlist and strict safety checks."""

from __future__ import annotations

import subprocess
from typing import Any, Dict, List

from backend.tools import BaseTool, register_tool


class ShellExecTool:
    name = "shell_exec"
    description = "Execute safe, pre-validated shell commands."

    DEFAULT_ALLOW = ["dir", "pip list", "pip show", "python ", "echo "]
    FORBIDDEN_TOKENS = ["&&", "||", ";", ">", "<", "|", "%", "`", "$("]
    FORBIDDEN_KEYWORDS = ["rm", "del", "shutdown", "reboot", "format", "mkfs", "poweroff"]
    MAX_OUTPUT_CHARS = 4000
    TIMEOUT_SECONDS = 15

    def _truncate(self, text: str) -> str:
        if len(text) <= self.MAX_OUTPUT_CHARS:
            return text
        return text[: self.MAX_OUTPUT_CHARS] + "...(truncated)"

    def _is_allowed(self, cmd: str, allowlist: List[str]) -> bool:
        cl = cmd.lower().strip()
        return any(cl.startswith(item.lower()) for item in allowlist)

    def _has_forbidden(self, cmd: str) -> bool:
        lower = cmd.lower()
        if any(tok in cmd for tok in self.FORBIDDEN_TOKENS):
            return True
        parts = lower.replace("/", " ").replace("\\", " ").split()
        return any(k in parts for k in self.FORBIDDEN_KEYWORDS)

    def run(self, command: str, allowed: List[str] | None = None, **kwargs: Any) -> Dict[str, Any]:
        cmd = (kwargs.get("command") or command or "").strip()
        if not cmd:
            return {"status": "error", "message": "No command provided."}

        allowlist = allowed or self.DEFAULT_ALLOW
        if self._has_forbidden(cmd):
            return {"status": "error", "message": "Command contains forbidden tokens/keywords.", "command": cmd}
        if not self._is_allowed(cmd, allowlist):
            return {"status": "error", "message": "Command not allowed", "command": cmd, "allowed": allowlist}

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                shell=True,
                timeout=self.TIMEOUT_SECONDS,
            )
            stdout = self._truncate(result.stdout.strip())
            stderr = self._truncate(result.stderr.strip())
            return {
                "status": "ok",
                "command": cmd,
                "stdout": stdout,
                "stderr": stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "command": cmd, "message": "Command timed out."}
        except Exception as e:
            return {"status": "error", "command": cmd, "message": str(e)}


register_tool(ShellExecTool())
