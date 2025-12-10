"""
Memory manager skeleton for long-term storage (e.g., SQLite-backed).
"""

from __future__ import annotations

from typing import List

from backend.core.types import AgentMessage


class MemoryManager:
    """
    Placeholder for persisting and retrieving conversation snippets or embeddings.
    """

    def __init__(self) -> None:
        self._store: list[AgentMessage] = []

    def save(self, message: AgentMessage) -> None:
        self._store.append(message)

    def load_recent(self, limit: int = 50) -> List[AgentMessage]:
        return self._store[-limit:]
