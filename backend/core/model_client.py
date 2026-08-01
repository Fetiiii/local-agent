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
                 temperature: Optional[float] = None):
        self.model_name = model_name or settings.model_name
        self.provider_name = (provider or settings.llm_provider or "ollama").lower()
        # Per-instance temperature override (e.g. from the UI); else settings default.
        self.temperature = temperature if temperature is not None else settings.temperature
        self.provider = build_provider(self.provider_name, self.model_name)
        print(f"🤖 Model Client ready: {self.model_name} (provider={self.provider_name})")

    def _build_options(self) -> Dict:
        return {
            "temperature": self.temperature,
            "num_ctx": settings.num_ctx,
            "keep_alive": -1,
        }

    async def generate(
        self,
        messages: List[Dict[str, str]],
        stream: bool = True,
        json_mode: bool = False,
        schema: Optional[Dict] = None,
    ) -> Union[AsyncGenerator[str, None], str]:
        options = self._build_options()
        return await self.provider.generate(
            messages, options=options, stream=stream, json_mode=json_mode, schema=schema
        )

    async def check_connection(self) -> bool:
        return await self.provider.check_connection()
