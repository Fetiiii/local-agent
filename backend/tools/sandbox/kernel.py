"""
SandboxKernel — host-side client for the persistent data_analyst driver that
runs inside the sandbox container (see da_driver.py).

Communicates over the shared /workspace volume: writes request files, waits for
response files. Reconstructs artifacts (plotly JSON, DataFrame CSV, PNG) into
objects/paths the sidebar already understands.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from typing import Dict, List

from backend.tools.sandbox.docker_sandbox import sandbox, _WORKSPACE_HOST, _WORKSPACE_CONTAINER

_CONTROL_HOST = _WORKSPACE_HOST / ".da_control"
_DRIVER_IN_CONTAINER = "/opt/da_driver.py"


def _to_host_path(container_path: str) -> str:
    """Map a /workspace/... container path to its host equivalent."""
    prefix = _WORKSPACE_CONTAINER.rstrip("/") + "/"
    if container_path.startswith(prefix):
        return str(_WORKSPACE_HOST / container_path[len(prefix):])
    return container_path


class SandboxKernel:
    def __init__(self):
        self._driver_cid: Dict[str, str] = {}
        self._locks: Dict[str, asyncio.Lock] = {}

    def _lock_for(self, session_id: str) -> asyncio.Lock:
        lock = self._locks.get(session_id)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[session_id] = lock
        return lock

    async def _ensure_driver(self, session_id: str) -> bool:
        """Ensure the container is up and the driver is running in it."""
        name = await sandbox.ensure_container(session_id)
        if not name:
            return False
        code, cid = await sandbox._run("inspect", "-f", "{{.Id}}", name, timeout=10)
        cid = cid.strip()
        # (Re)start the driver whenever the container is new/changed.
        if self._driver_cid.get(session_id) != cid:
            _CONTROL_HOST.mkdir(parents=True, exist_ok=True)
            # Clear stale control files left on the host volume by a prior session.
            for f in _CONTROL_HOST.glob("*.json"):
                try:
                    f.unlink()
                except OSError:
                    pass
            await sandbox._run("exec", "-d", name, "python", _DRIVER_IN_CONTAINER, timeout=15)
            self._driver_cid[session_id] = cid
            await asyncio.sleep(0.4)  # let the driver create its dirs
        return True

    async def execute(self, session_id: str, code: str, timeout: int = 60) -> Dict:
        """
        Run code in the session's persistent sandbox kernel.
        Returns {"stdout", "artifacts" (host-side manifest), "error"}.
        """
        async with self._lock_for(session_id):
            if not await self._ensure_driver(session_id):
                return {"stdout": "", "artifacts": [],
                        "error": "Sandbox kernel unavailable (container/driver could not start)."}

            rid = uuid.uuid4().hex
            req_path = _CONTROL_HOST / f"req-{rid}.json"
            resp_path = _CONTROL_HOST / f"resp-{rid}.json"

            # Atomic write so the driver never reads a partial request.
            tmp = req_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps({"id": rid, "code": code, "timeout": timeout}))
            os.replace(tmp, req_path)

            # Wait for the response (driver enforces the real code timeout).
            deadline = asyncio.get_event_loop().time() + timeout + 20
            while asyncio.get_event_loop().time() < deadline:
                if resp_path.exists():
                    break
                await asyncio.sleep(0.05)
            else:
                req_path.unlink(missing_ok=True)
                return {"stdout": "", "artifacts": [],
                        "error": f"Sandbox kernel did not respond within {timeout + 20}s."}

            try:
                resp = json.loads(resp_path.read_text())
            except Exception as e:  # noqa: BLE001
                return {"stdout": "", "artifacts": [], "error": f"Bad kernel response: {e}"}
            finally:
                resp_path.unlink(missing_ok=True)

            # Map artifact container paths to host paths.
            for art in resp.get("artifacts", []):
                if "path" in art:
                    art["path"] = _to_host_path(art["path"])
            return resp


kernel = SandboxKernel()
