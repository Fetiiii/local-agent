"""
Manage the lifecycle of a local llama.cpp server process.
Transport details are TBD; this skeleton just defines the shape.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional


class LlamaServerManager:
    def __init__(self, binary_path: Path | str = "llama.cpp", model_path: Path | str = "llama/models/model.gguf"):
        self.binary_path = Path(binary_path)
        self.model_path = Path(model_path)
        self.process: Optional[subprocess.Popen] = None

    def start(self, host: str = "127.0.0.1", port: int = 8080, mode_params: dict | None = None) -> None:
        """
        Launch the llama.cpp server with given parameters.
        This is a placeholder; adapt args to your build of llama.cpp server.
        """
        if self.process and self.process.poll() is None:
            return  # Already running

        args = [
            str(self.binary_path),
            "--host",
            host,
            "--port",
            str(port),
            "--model",
            str(self.model_path),
        ]
        if mode_params:
            args.extend(self._mode_params_to_args(mode_params))

        # TODO: replace with the correct llama.cpp server command.
        self.process = subprocess.Popen(args)

    def stop(self) -> None:
        """Terminate the server process if running."""
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.process.wait(timeout=10)
        self.process = None

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    @staticmethod
    def _mode_params_to_args(params: dict) -> list[str]:
        """Translate mode JSON fields into CLI args for llama.cpp."""
        args: list[str] = []
        if "context_size" in params:
            args.extend(["--ctx-size", str(params["context_size"])])
        if "temperature" in params:
            args.extend(["--temp", str(params["temperature"])])
        if "n_gpu_layers" in params:
            args.extend(["--n-gpu-layers", str(params["n_gpu_layers"])])
        return args
