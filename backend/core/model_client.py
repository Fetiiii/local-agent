"""
ModelClient — thin, backend-agnostic facade over an LLMProvider.

Public API is unchanged (generate / check_connection) so the rest of the app
keeps working, but the actual runtime (Ollama, llama.cpp via OpenAI-compatible
API, …) is chosen from settings.
"""

from __future__ import annotations

from typing import AsyncGenerator, Dict, List, Optional, Union

from backend.core.settings import settings
from backend.core.providers import build_provider


class ModelClient:
    def __init__(self, model_name: Optional[str] = None, provider: Optional[str] = None,
                 temperature: Optional[float] = None, top_p: Optional[float] = None,
                 max_tokens: Optional[int] = None):
        self.model_name = model_name or settings.model_name
        self.provider_name = (provider or settings.llm_provider or "ollama").lower()
        # Per-instance overrides (e.g. from the UI settings panel); else defaults.
        self.temperature = temperature if temperature is not None else settings.temperature
        self.top_p = top_p                 # None → provider default
        self.max_tokens = max_tokens       # None/0 → unlimited
        self.provider = build_provider(self.provider_name, self.model_name)
        print(f"🤖 Model Client ready: {self.model_name} (provider={self.provider_name})")

    def _build_options(self) -> Dict:
        opts: Dict = {
            "temperature": self.temperature,
            "num_ctx": settings.num_ctx,
            "keep_alive": -1,
        }
        if self.top_p is not None:
            opts["top_p"] = self.top_p
        if self.max_tokens:
            opts["max_tokens"] = self.max_tokens
        return opts

    async def generate(
        self,
        messages: List[Dict[str, str]],
        stream: bool = True,
        json_mode: bool = False,
        schema: Optional[Dict] = None,
        max_tokens: Optional[int] = None,
    ) -> Union[AsyncGenerator[str, None], str]:
        options = self._build_options()
        if max_tokens:
            options["max_tokens"] = max_tokens   # per-call cap (overrides instance/unlimited)
        return await self.provider.generate(
            messages, options=options, stream=stream, json_mode=json_mode, schema=schema
        )

    async def check_connection(self) -> bool:
        return await self.provider.check_connection()
