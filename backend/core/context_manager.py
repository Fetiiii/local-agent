"""
Context management skeleton: handles recent history trimming and summary placeholders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from backend.core.types import AgentMessage
from backend.core import summarizer
from backend.core.memory_manager import MemoryManager


@dataclass
class ContextManager:
    history: List[AgentMessage] = field(default_factory=list)
    max_tokens: int = 4096  # placeholder for future token-based trimming
    summary_every: int = 50
    memory: Optional[MemoryManager] = None

    def append_message(self, message: AgentMessage) -> None:
        self.history.append(message)
        if self.memory:
            self.memory.save(message)
        if len(self.history) >= self.summary_every:
            self._maybe_summarize()

    def get_recent_history(self, limit: int = 20) -> List[AgentMessage]:
        """Return a shallow copy of the last N messages."""
        return self.history[-limit:]

    def trim_history(self, messages: List[AgentMessage]) -> List[AgentMessage]:
        """
        Placeholder trimming: currently returns input.
        Later replace with token-based windowing and rolling summaries.
        """
        return messages

    def set_history(self, messages: List[AgentMessage]) -> None:
        """Replace current history with provided messages."""
        self.history = list(messages)

    def reset(self) -> None:
        self.history = []

    def add_summary_placeholder(self) -> None:
        """
        Insert a summary placeholder into history.
        """
        summary_message = AgentMessage(
            role="system",
            content="TODO: conversation summary placeholder",
            meta={"type": "summary"},
        )
        self.append_message(summary_message)

    def _maybe_summarize(self) -> None:
        """
        If history is long, append a summarization message and trim.
        """
        if len(self.history) < self.summary_every:
            return
        summary_msg = summarizer.summarize_history(self.history[-self.summary_every :])
        self.history = self.history[-self.summary_every :] + [summary_msg]
