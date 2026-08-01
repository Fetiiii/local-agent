"""
OpenAIProvider — talks to any OpenAI-compatible /v1/chat/completions endpoint.

Works with llama.cpp's `llama-server`, LM Studio, vLLM, text-generation-webui,
and the real OpenAI API. This is what lets small GGUF models served by
llama.cpp plug into the same agent loop as Ollama.
"""

from __future__ import annotations

from typing import AsyncGenerator, Dict, List, Optional, Union

from openai import AsyncOpenAI

from backend.core.providers.base import LLMProvider


class OpenAIProvider(LLMProvider):
    def __init__(self, model_name: str, base_url: str, api_key: str = "not-needed"):
        super().__init__(model_name)
        # llama-server ignores the key, but the SDK requires a non-empty value.
        self.client = AsyncOpenAI(base_url=base_url, api_key=api_key or "not-needed")
        self.base_url = base_url
        print(f"🤖 OpenAIProvider ready: {self.model_name} @ {base_url}")

    def _build_kwargs(self, messages, options, json_mode, schema) -> Dict:
        kwargs: Dict = {
            "model": self.model_name,
            "messages": messages,
            "temperature": options.get("temperature", 0.7),
        }
        # num_ctx has no direct OpenAI equivalent; the server owns the context
        # window. We can still cap generation length if provided.
        if options.get("max_tokens"):
            kwargs["max_tokens"] = options["max_tokens"]
        # Structured outputs: a JSON schema constrains the output far more
        # reliably than plain json_object (crucial for small local models).
        if schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "structured_output", "schema": schema, "strict": False},
            }
        elif json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        return kwargs

    async def generate(
        self,
        messages: List[Dict[str, str]],
        options: Dict,
        stream: bool = True,
        json_mode: bool = False,
        schema: Optional[Dict] = None,
    ) -> Union[AsyncGenerator[str, None], str]:
        kwargs = self._build_kwargs(messages, options, json_mode, schema)

        if stream:
            return self._stream(kwargs)

        try:
            resp = await self.client.chat.completions.create(**kwargs, stream=False)
            return resp.choices[0].message.content or ""
        except Exception as e:
            # Some servers don't support json_schema; degrade gracefully:
            # json_schema -> json_object -> no response_format.
            rf = kwargs.get("response_format")
            if rf and rf.get("type") == "json_schema":
                print(f"⚠️ json_schema rejected: {e}. Falling back to json_object...")
                kwargs["response_format"] = {"type": "json_object"}
                try:
                    resp = await self.client.chat.completions.create(**kwargs, stream=False)
                    return resp.choices[0].message.content or ""
                except Exception as e2:
                    print(f"⚠️ json_object also rejected: {e2}. Dropping response_format...")
                    kwargs.pop("response_format", None)
                    resp = await self.client.chat.completions.create(**kwargs, stream=False)
                    return resp.choices[0].message.content or ""
            if rf:
                print(f"⚠️ response_format rejected: {e}. Retrying without it...")
                kwargs.pop("response_format", None)
                resp = await self.client.chat.completions.create(**kwargs, stream=False)
                return resp.choices[0].message.content or ""
            return f"Error communicating with OpenAI-compatible endpoint: {e}"

    async def _stream(self, kwargs) -> AsyncGenerator[str, None]:
        stream = await self.client.chat.completions.create(**kwargs, stream=True)
        async for chunk in stream:
            if not chunk.choices:
                continue
            content = chunk.choices[0].delta.content
            if content:
                yield content

    async def check_connection(self) -> bool:
        try:
            await self.client.models.list()
            return True
        except Exception:
            return False
