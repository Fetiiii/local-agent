"""OllamaProvider — talks to a local Ollama daemon via the official async client."""

from __future__ import annotations

from typing import AsyncGenerator, Dict, List, Optional, Union

import ollama

from backend.core.providers.base import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self, model_name: str):
        super().__init__(model_name)
        self.client = ollama.AsyncClient()
        print(f"🤖 OllamaProvider ready: {self.model_name}")

    def _map_options(self, options: Dict) -> Dict:
        """Translate normalized options into Ollama's options dict."""
        mapped = {
            "temperature": options.get("temperature", 0.7),
            "num_ctx": options.get("num_ctx", 8192),
        }
        if options.get("top_p") is not None:
            mapped["top_p"] = options["top_p"]
        if options.get("max_tokens"):
            mapped["num_predict"] = options["max_tokens"]
        if "keep_alive" in options:
            mapped["keep_alive"] = options["keep_alive"]
        return mapped

    async def generate(
        self,
        messages: List[Dict[str, str]],
        options: Dict,
        stream: bool = True,
        json_mode: bool = False,
        schema: Optional[Dict] = None,
    ) -> Union[AsyncGenerator[str, None], str]:
        mapped = self._map_options(options)
        # Ollama structured outputs: pass a JSON schema dict as `format`.
        # Falls back to plain "json" mode, or None for free-form text.
        if schema is not None:
            format_param = schema
        elif json_mode:
            format_param = "json"
        else:
            format_param = None

        if stream:
            return self._stream(messages, mapped, format_param)

        try:
            response = await self.client.chat(
                model=self.model_name,
                messages=messages,
                options=mapped,
                format=format_param,
                stream=False,
            )
            return response["message"]["content"]
        except Exception as e:
            # Ollama's JSON mode can choke on very large responses; retry raw.
            if json_mode and "parsing" in str(e).lower():
                print(f"⚠️ Ollama JSON parse error: {e}. Falling back to raw mode...")
                response = await self.client.chat(
                    model=self.model_name,
                    messages=messages,
                    options=mapped,
                    stream=False,
                )
                return response["message"]["content"]
            return f"Error communicating with Ollama: {e}"

    async def _stream(self, messages, options, format_param) -> AsyncGenerator[str, None]:
        stream = await self.client.chat(
            model=self.model_name,
            messages=messages,
            options=options,
            format=format_param,
            stream=True,
        )
        async for chunk in stream:
            content = chunk["message"]["content"]
            if content:
                yield content

    async def check_connection(self) -> bool:
        try:
            await self.client.list()
            return True
        except Exception:
            return False
