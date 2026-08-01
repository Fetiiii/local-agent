"""Provider factory — builds the right LLMProvider from settings."""

from __future__ import annotations

from backend.core.providers.base import LLMProvider
from backend.core.providers.ollama_provider import OllamaProvider
from backend.core.providers.openai_provider import OpenAIProvider

__all__ = ["LLMProvider", "OllamaProvider", "OpenAIProvider", "build_provider"]


def build_provider(provider_name: str, model_name: str) -> LLMProvider:
    """Instantiate a provider by name. Falls back to Ollama for unknown names."""
    from backend.core.settings import settings

    name = (provider_name or "ollama").strip().lower()

    if name == "openai":
        return OpenAIProvider(
            model_name=model_name,
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key or "not-needed",
        )
    # default / "ollama"
    return OllamaProvider(model_name=model_name)
