"""
Process utility placeholders for future use (health checks, graceful shutdowns).
"""

from __future__ import annotations

import subprocess
from typing import Optional


def is_process_alive(proc: Optional[subprocess.Popen]) -> bool:
    return proc is not None and proc.poll() is None


def terminate_process(proc: Optional[subprocess.Popen], timeout: int = 10) -> None:
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
