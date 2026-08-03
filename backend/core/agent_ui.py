"""
AgentUI — the transport-agnostic interface the agent core emits events to.

The agent never imports a UI framework; it only calls these methods. Each
frontend provides an adapter (WebSocket for the custom UI, and this is the seam
that lets us drop Chainlit). Keeps the core headless and testable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class AgentUI(ABC):
    @abstractmethod
    async def step(self, thought: Optional[str], plan: List[str]) -> None:
        """A reasoning step: the agent's thought + plan for this iteration."""

    async def thinking(self, text: str = "", done: bool = False, reset: bool = False) -> None:
        """Live reasoning delta streamed as the model produces its decision.
        `text` is appended to the current thought; `done=True` closes it;
        `reset=True` drops a partial thought (e.g. after a failed parse).
        Default no-op so non-streaming adapters keep working."""

    async def plan(self, plan: List[str]) -> None:
        """Live plan/to-do update as items are produced. Default no-op."""

    @abstractmethod
    async def tool_start(self, tool_id: str, name: str, args: Dict[str, Any]) -> None:
        """A tool is about to run."""

    @abstractmethod
    async def tool_end(self, tool_id: str, name: str, result: str,
                       artifacts: Optional[List[Dict]] = None) -> None:
        """A tool finished; result text + optional artifact descriptors."""

    @abstractmethod
    async def token(self, text: str) -> None:
        """A chunk of the streaming final answer."""

    @abstractmethod
    async def final(self, text: str) -> None:
        """The final answer is complete."""

    @abstractmethod
    async def notice(self, text: str, level: str = "info") -> None:
        """An informational or error message (level: info|warn|error)."""

    @abstractmethod
    async def ask_approval(self, title: str, detail: str) -> bool:
        """Human-in-the-loop: request approval, block until the user answers."""


class NullUI(AgentUI):
    """No-op UI for tests/headless runs (auto-approves)."""

    async def step(self, thought, plan): pass
    async def tool_start(self, tool_id, name, args): pass
    async def tool_end(self, tool_id, name, result, artifacts=None): pass
    async def token(self, text): pass
    async def final(self, text): pass
    async def notice(self, text, level="info"): pass
    async def ask_approval(self, title, detail): return True
