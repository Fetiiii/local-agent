"""
ShellExecutorTool — sandboxed asyncio subprocess runner.

Safety rules:
- Working directory is always resolved inside data/exports/ (or the
  user-supplied cwd if it falls under that root).
- A hard timeout of TIMEOUT_SECONDS terminates runaway processes.
- A small blocklist of obviously destructive commands is rejected up-front.
- stdout + stderr are merged and returned as a single string (capped at 8 kB).
"""

import asyncio
import os
import shlex
from pathlib import Path

from backend.core.settings import settings
from backend.tools.sandbox import sandbox, current_session_id

EXPORTS_ROOT = Path("data/exports").resolve()
TIMEOUT_SECONDS = 30
MAX_OUTPUT_BYTES = 8192

# Commands that are too dangerous to ever run via the agent.
BLOCKED_PREFIXES = (
    "rm -rf /",
    "del /s /q c:\\",
    "format ",
    "shutdown",
    "reboot",
    "mkfs",
    "dd if=",
)


class ShellExecutorTool:
    """Executes shell commands in a sandboxed working directory."""

    name = "shell_executor"
    description = (
        "Run a shell / terminal command and return its stdout + stderr. "
        "Runs inside an isolated Docker sandbox (working dir /workspace, which "
        "maps to data/exports/ on the host). Use this for: pip install, npm, "
        "git, running scripts, etc."
    )

    # --- Tool schema for ToolRegistry ---
    def get_schema(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute (e.g. 'pip install pandas').",
                    },
                    "cwd": {
                        "type": "string",
                        "description": (
                            "Optional sub-directory inside data/exports/ to run from. "
                            "Defaults to data/exports/."
                        ),
                    },
                    "timeout": {
                        "type": "integer",
                        "description": f"Max seconds to wait. Defaults to {TIMEOUT_SECONDS}.",
                    },
                },
                "required": ["command"],
            },
        }

    async def run(self, command: str, cwd: str = None, timeout: int = TIMEOUT_SECONDS) -> str:
        # --- Safety: blocklist (defense-in-depth; primary isolation is the sandbox) ---
        cmd_lower = command.strip().lower()
        for blocked in BLOCKED_PREFIXES:
            if cmd_lower.startswith(blocked):
                return f"❌ Blocked command: '{command}' matches blocklist pattern '{blocked}'."

        # --- Sandbox path: run inside an isolated Docker container when enabled ---
        backend = settings.sandbox_backend.lower()
        if sandbox.should_use():
            if await sandbox.is_available():
                # Docker is present → the command MUST stay sandboxed. Return
                # whatever the sandbox produced (result or error); never silently
                # fall back to unsandboxed host execution on a container hiccup.
                _, out = await sandbox.exec(
                    current_session_id(), command, timeout=timeout, workdir=cwd
                )
                return out
            elif backend == "docker":
                return (
                    "❌ SANDBOX_BACKEND=docker but Docker is unavailable. "
                    "Refusing to run the command on the host."
                )
            # backend == "auto" and Docker missing → fall through to host execution.

        # --- Safety: resolve working directory (host fallback) ---
        if cwd:
            resolved_cwd = (EXPORTS_ROOT / cwd).resolve()
        else:
            resolved_cwd = EXPORTS_ROOT

        # Ensure the resolved cwd stays inside EXPORTS_ROOT
        try:
            resolved_cwd.relative_to(EXPORTS_ROOT)
        except ValueError:
            return (
                f"❌ Security error: cwd '{cwd}' resolves outside of "
                f"data/exports/. Command refused."
            )

        resolved_cwd.mkdir(parents=True, exist_ok=True)

        # --- Execute ---
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,  # merge stderr into stdout
                cwd=str(resolved_cwd),
            )

            try:
                raw_output, _ = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                return (
                    f"⏰ Command timed out after {timeout}s and was killed.\n"
                    f"Command: {command}"
                )

            output = raw_output.decode("utf-8", errors="replace")

            # Cap output length
            if len(output.encode()) > MAX_OUTPUT_BYTES:
                output = output[: MAX_OUTPUT_BYTES // 2] + "\n… [output truncated] …"

            exit_code = process.returncode
            status = "✅" if exit_code == 0 else f"⚠️ (exit code {exit_code})"
            return f"{status} CWD: {resolved_cwd}\n\n```\n{output.strip()}\n```"

        except FileNotFoundError:
            return f"❌ Command not found: '{command.split()[0]}'. Is it installed?"
        except Exception as e:
            return f"❌ Shell execution error: {e}"
