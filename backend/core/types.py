from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class AgentMessage:
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    meta: Dict[str, Any] = field(default_factory=dict)
