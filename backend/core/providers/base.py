"""
LLMProvider — backend-agnostic abstraction over a chat/completion model.

Each concrete provider (Ollama, OpenAI-compatible, …) implements the same
`generate` / `check_connection` contract so the rest of the app never has to
know which runtime is actually serving the model.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Optional, Union


class LLMProvider(ABC):
    """Common interface every model backend must implement."""

    def __init__(self, model_name: str):
        self.model_name = model_name

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        options: Dict,
        stream: bool = True,
        json_mode: bool = False,
        schema: Optional[Dict] = None,
    ) -> Union[AsyncGenerator[str, None], str]:
        """
        Run a chat completion.

        Args:
            messages: [{"role": ..., "content": ...}, ...]
            options: normalized generation options: {temperature, num_ctx, keep_alive}
            stream: if True return an async generator of text chunks, else a full string.
            json_mode: if True, ask the backend to constrain output to JSON.
            schema: optional JSON Schema (dict) to constrain output structure
                (structured outputs). Takes precedence over plain json_mode when
                the backend supports it.

        Returns:
            AsyncGenerator[str] when stream=True, otherwise the full response str.
        """
        raise NotImplementedError

    @abstractmethod
    async def check_connection(self) -> bool:
        """Return True if the backend is reachable."""
        raise NotImplementedError
