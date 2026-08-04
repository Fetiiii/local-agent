"""
LlamaManager — lets the web server start / stop / switch the llama.cpp
`llama-server` so the UI can pick between local .gguf models.

llama.cpp serves ONE model per process, so "switching models" means relaunching
llama-server with a different .gguf. This manager owns that process: it lists the
models in a folder, auto-attaches a matching `mmproj-*.gguf` (vision), and hot-
swaps on request. Only active when llm_provider="openai" and manage_llama_server.
"""
from __future__ import annotations

import os
import re
import shutil
import asyncio
import subprocess
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse

from backend.core.settings import settings

_QUANT_TOKENS = re.compile(r"(?i)^(q\d.*|iq\d.*|f16|f32|bf16|k_m|k_s|k_l|ud|xxs|xs|s|m|l|gguf)$")


def _tokens(name: str) -> set:
    """Family tokens of a model filename, minus quant/format noise, for matching."""
    stem = Path(name).stem
    return {t for t in re.split(r"[-_.]", stem) if t and not _QUANT_TOKENS.match(t)}


class LlamaManager:
    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None   # our child, if we started it
        self._current: Optional[str] = None             # current model filename
        self._lock = asyncio.Lock()
        u = urlparse(settings.openai_base_url)
        self._host = u.hostname or "127.0.0.1"
        self._port = u.port or 8080

    # ── discovery ─────────────────────────────────────────────────────────────
    def models_dir(self) -> Optional[Path]:
        if settings.models_dir:
            p = Path(settings.models_dir).expanduser()
        elif settings.model_name:
            p = Path(settings.model_name).expanduser().parent
        else:
            return None
        return p if p.is_dir() else None

    def list_models(self) -> List[str]:
        d = self.models_dir()
        if not d:
            return []
        out = [f.name for f in d.glob("*.gguf") if not f.name.lower().startswith("mmproj")]
        return sorted(out)

    def current(self) -> Optional[str]:
        if self._current:
            return self._current
        if settings.model_name:
            return Path(settings.model_name).name
        return None

    def _bin(self) -> Optional[str]:
        if settings.llama_server_bin and os.path.isfile(settings.llama_server_bin):
            return settings.llama_server_bin
        found = shutil.which("llama-server")
        if found:
            return found
        cand = Path.home() / "llama.cpp" / "build" / "bin" / "llama-server"
        return str(cand) if cand.is_file() else None

    def _mmproj_for(self, model_file: str) -> Optional[Path]:
        """Best-matching mmproj (highest family-token overlap, >=2) or None."""
        d = self.models_dir()
        if not d:
            return None
        want = _tokens(model_file)
        best, best_n = None, 1
        for f in d.glob("mmproj*.gguf"):
            n = len(want & _tokens(f.name))
            if n > best_n:
                best, best_n = f, n
        return best

    # ── health ────────────────────────────────────────────────────────────────
    def _healthy(self) -> bool:
        try:
            with urllib.request.urlopen(f"http://{self._host}:{self._port}/health", timeout=2) as r:
                return r.status == 200
        except Exception:
            return False

    async def _wait_healthy(self, timeout: int = 180) -> bool:
        for _ in range(timeout):
            if self._healthy():
                return True
            await asyncio.sleep(1)
        return False

    # ── lifecycle ─────────────────────────────────────────────────────────────
    def _stop(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None
        # If a server is still on the port (started externally), free it too.
        if self._healthy():
            subprocess.run(["fuser", "-k", "-TERM", f"{self._port}/tcp"],
                           stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)

    def _start(self, model_path: Path) -> None:
        binary = self._bin()
        if not binary or not model_path.is_file():
            raise RuntimeError(f"llama-server binary or model not found (bin={binary}, model={model_path})")
        cmd = [binary, "-m", str(model_path),
               "--host", self._host, "--port", str(self._port),
               "-c", str(settings.num_ctx), "--jinja"]
        mmproj = self._mmproj_for(model_path.name)
        if mmproj:
            cmd += ["--mmproj", str(mmproj)]
        if settings.llama_server_args:
            cmd += settings.llama_server_args.split()
        logs = Path("logs"); logs.mkdir(exist_ok=True)
        with open(logs / "llama-server.log", "ab") as log:
            self._proc = subprocess.Popen(cmd, stdout=log, stderr=log)
        self._current = model_path.name

    async def ensure_started(self) -> None:
        """On boot: adopt a running server, else start the default model."""
        if not settings.manage_llama_server:
            return
        async with self._lock:
            if self._healthy():
                self._current = self.current()   # adopt (from settings.model_name)
                return
            d = self.models_dir()
            default = None
            if settings.model_name:
                default = Path(settings.model_name).expanduser()
            elif d:
                names = self.list_models()
                default = d / names[0] if names else None
            if default and default.is_file():
                try:
                    self._start(default)
                    await self._wait_healthy()
                except Exception as e:
                    print(f"⚠️ llama-server otomatik başlatılamadı: {e}")

    async def switch(self, model_name: str) -> dict:
        if not settings.manage_llama_server:
            return {"ok": False, "error": "manage_llama_server kapalı."}
        d = self.models_dir()
        if not d:
            return {"ok": False, "error": "models_dir bulunamadı."}
        target = d / model_name
        if model_name.lower().startswith("mmproj") or not target.is_file() or target.suffix != ".gguf":
            return {"ok": False, "error": f"Geçersiz model: {model_name}"}
        if model_name == self._current and self._healthy():
            return {"ok": True, "model": model_name, "note": "zaten yüklü"}
        async with self._lock:
            self._stop()
            try:
                self._start(target)
            except Exception as e:
                return {"ok": False, "error": str(e)}
            if not await self._wait_healthy():
                return {"ok": False, "error": "model yüklendi ama /health yanıt vermedi."}
        return {"ok": True, "model": model_name}

    def shutdown(self) -> None:
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._proc.kill()


llama_manager = LlamaManager()
