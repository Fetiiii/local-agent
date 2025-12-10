"""
Mode switcher skeleton: loads mode configs and manages server parameter changes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

from backend.server_control.llama_server_manager import LlamaServerManager


class ModeSwitcher:
    def __init__(self, modes_dir: Path | str, server: LlamaServerManager) -> None:
        self.modes_dir = Path(modes_dir)
        self.server = server
        self.modes: Dict[str, dict] = self._load_modes()
        self.current_mode = "default"

    def _load_modes(self) -> Dict[str, dict]:
        modes: Dict[str, dict] = {}
        for path in self.modes_dir.glob("*.json"):
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                modes[data["name"]] = data
        return modes

    def set_mode(self, mode_name: str) -> dict:
        """
        Update current mode and restart/reconfigure server with new params.
        """
        if mode_name not in self.modes:
            raise ValueError(f"Unknown mode: {mode_name}")
        self.current_mode = mode_name
        params = self.modes[mode_name]
        # TODO: consider hot reload vs. restart. For now, restart server with args.
        if self.server.is_running():
            self.server.stop()
        self.server.start(mode_params=params)
        return params
