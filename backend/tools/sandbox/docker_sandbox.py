"""
DockerSandbox — runs untrusted commands inside a hardened, per-session Docker
container so model-generated code can never touch the host filesystem, network
(by default), or processes.

One long-lived container per Chainlit session (lazily created, reused across
calls, destroyed on session end). Commands are injected with `docker exec`.
Installed packages and files therefore persist for the whole session and are
shared between shell_executor and (phase B) data_analyst.
"""

from __future__ import annotations

import asyncio
import re
import shlex
from pathlib import Path
from typing import Optional, Tuple

from backend.core.settings import settings

# Host directory shared into every sandbox at /workspace.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_WORKSPACE_HOST = _PROJECT_ROOT / "data" / "exports"
_WORKSPACE_CONTAINER = "/workspace"

_NAME_PREFIX = "localagent-sbx-"
_MAX_OUTPUT_BYTES = 8192


def current_session_id() -> str:
    """Best-effort Chainlit session id; falls back to a shared id off-session."""
    try:
        import chainlit as cl
        sid = cl.context.session.id
        if sid:
            return str(sid)
    except Exception:
        pass
    return "default"


def _safe_name(session_id: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_.-]", "-", session_id)[:48]
    return f"{_NAME_PREFIX}{slug or 'default'}"


class DockerSandbox:
    def __init__(self):
        self._available: Optional[bool] = None
        # Per-session locks serialize container creation so parallel tool calls
        # (asyncio.gather) don't race to `docker run` the same container name.
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, session_id: str) -> asyncio.Lock:
        # No await here → atomic under the single-threaded event loop.
        lock = self._locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[session_id] = lock
        return lock

    # ── Availability ─────────────────────────────────────────────────────────

    async def is_available(self) -> bool:
        """Cached check that the Docker daemon is reachable."""
        if self._available is not None:
            return self._available
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "info",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=10)
            self._available = proc.returncode == 0
        except Exception:
            self._available = False
        return self._available

    def should_use(self) -> bool:
        """Whether the configured backend wants Docker at all."""
        return settings.sandbox_backend.lower() in ("auto", "docker")

    # ── Container lifecycle ──────────────────────────────────────────────────

    async def _run(self, *args, timeout: int = 30) -> Tuple[int, str]:
        proc = await asyncio.create_subprocess_exec(
            "docker", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return 124, "docker command timed out"
        return proc.returncode, out.decode("utf-8", errors="replace")

    async def _is_running(self, name: str) -> bool:
        code, out = await self._run(
            "inspect", "-f", "{{.State.Running}}", name, timeout=10
        )
        return code == 0 and out.strip() == "true"

    async def ensure_container(self, session_id: str) -> Optional[str]:
        """Create (or reuse) the session container. Returns its name, or None on failure."""
        name = _safe_name(session_id)
        # Serialize so concurrent tool calls don't both try to create it.
        async with self._lock_for(session_id):
            if await self._is_running(name):
                return name
            return await self._create_container(name)

    async def _create_container(self, name: str) -> Optional[str]:
        # Remove any stale container with this name (stopped/exited).
        await self._run("rm", "-f", name, timeout=15)

        _WORKSPACE_HOST.mkdir(parents=True, exist_ok=True)

        network = "bridge" if settings.sandbox_allow_network else "none"
        args = [
            "run", "-d", "--name", name,
            "--label", "app=localagent-sandbox",
            "--network", network,
            "--memory", settings.sandbox_memory,
            "--cpus", settings.sandbox_cpus,
            "--pids-limit", str(settings.sandbox_pids_limit),
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "-v", f"{_WORKSPACE_HOST}:{_WORKSPACE_CONTAINER}",
            "-w", _WORKSPACE_CONTAINER,
            settings.sandbox_image,
        ]
        code, out = await self._run(*args, timeout=60)
        if code != 0:
            print(f"❌ Sandbox container start failed: {out.strip()}")
            return None
        return name

    async def destroy(self, session_id: str):
        await self._run("rm", "-f", _safe_name(session_id), timeout=20)

    # ── Command execution ────────────────────────────────────────────────────

    async def exec(self, session_id: str, command: str, timeout: int = 30,
                   workdir: Optional[str] = None) -> Tuple[bool, str]:
        """
        Run a shell command inside the session container.
        Returns (ok, output). `ok` is False if the sandbox itself failed to run.
        """
        name = await self.ensure_container(session_id)
        if not name:
            return False, "❌ Sandbox unavailable (container could not start)."

        wd = _WORKSPACE_CONTAINER
        if workdir:
            # Keep workdir inside the workspace mount.
            candidate = (Path(_WORKSPACE_CONTAINER) / workdir).as_posix()
            if candidate.startswith(_WORKSPACE_CONTAINER):
                wd = candidate

        # `timeout` (coreutils) reliably kills the process tree inside the container.
        inner = f"timeout {int(timeout)} sh -c {shlex.quote(command)}"
        # Add a small margin so our await doesn't fire before coreutils timeout.
        code, out = await self._run(
            "exec", "-w", wd, name, "sh", "-c", inner, timeout=timeout + 10
        )

        if len(out.encode()) > _MAX_OUTPUT_BYTES:
            out = out[: _MAX_OUTPUT_BYTES // 2] + "\n… [output truncated] …"

        if code == 124:
            return True, f"⏰ Command timed out after {timeout}s (killed inside sandbox)."
        status = "✅" if code == 0 else f"⚠️ (exit code {code})"
        net = "off" if not settings.sandbox_allow_network else "on"
        return True, f"{status} [🐳 sandbox, net:{net}] CWD: {wd}\n\n```\n{out.strip()}\n```"


# Module-level singleton.
sandbox = DockerSandbox()
