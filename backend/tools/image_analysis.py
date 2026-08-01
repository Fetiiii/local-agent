"""
ImageAnalysisTool — provider-aware vision analysis.

Routes through the configured vision backend instead of being hard-wired to
Ollama:
  • "openai"  → OpenAI-compatible chat completions with image_url content parts
                (works with a llama.cpp `llama-server` launched with --mmproj,
                or the real OpenAI API).
  • "ollama"  → Ollama vision model (images in the chat message).

Vision can use a different backend than the main text model (VISION_PROVIDER /
VISION_BASE_URL / VISION_MODEL). Falls back to the main LLM provider/endpoint.
"""

from __future__ import annotations

import base64
import mimetypes
import os
from typing import Any, Dict, List, Optional

from backend.core.settings import settings


class ImageAnalysisTool:
    name = "image_analysis"
    description = (
        "Analyze one or more images with a vision model. Provide 'image_path' "
        "(or 'image_paths' for several) and a 'prompt' asking about the image(s)."
    )

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.vision_model

    # ── helpers ────────────────────────────────────────────────────────────────

    def _provider(self) -> str:
        return (settings.vision_provider or settings.llm_provider or "ollama").lower()

    @staticmethod
    def _encode(path: str) -> str:
        with open(path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    @staticmethod
    def _mime(path: str) -> str:
        return mimetypes.guess_type(path)[0] or "image/png"

    # ── entrypoint ──────────────────────────────────────────────────────────────

    async def run(
        self,
        image_path: Optional[str] = None,
        prompt: str = "Describe this image in detail.",
        image_paths: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        # Collect one or more image paths from the various arg shapes the model uses.
        paths: List[str] = []
        if image_paths:
            paths += image_paths if isinstance(image_paths, list) else [image_paths]
        single = image_path or kwargs.get("image_path") or kwargs.get("path")
        if single:
            paths.append(single)
        paths = [p for p in dict.fromkeys(paths) if p]  # dedupe, keep order

        if not paths:
            return {"text": "❌ Error: No image path provided.", "artifacts": []}
        missing = [p for p in paths if not os.path.exists(p)]
        if missing:
            return {"text": f"❌ Error: image(s) not found: {missing}", "artifacts": []}

        provider = self._provider()
        try:
            print(f"👁️ Visual Analysis ({provider}, {self.model_name})...")
            if provider == "openai":
                result = await self._run_openai(paths, prompt)
            else:
                result = await self._run_ollama(paths, prompt)
        except Exception as e:  # noqa: BLE001
            return {
                "text": (
                    f"❌ Vision error ({provider}): {e}\n"
                    "Is a vision model available? For llama.cpp, launch llama-server "
                    "with --mmproj; for Ollama, pull a vision model (e.g. qwen2.5vl)."
                ),
                "artifacts": paths,
            }

        return {"text": f"--- IMAGE ANALYSIS RESULT ---\n{result}", "artifacts": paths}

    # ── backends ────────────────────────────────────────────────────────────────

    async def _run_ollama(self, paths: List[str], prompt: str) -> str:
        import ollama

        client = ollama.AsyncClient()
        resp = await client.chat(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt,
                       "images": [self._encode(p) for p in paths]}],
            keep_alive=0,  # free the vision model from VRAM after the call
        )
        return resp["message"]["content"] or "No analysis generated."

    async def _run_openai(self, paths: List[str], prompt: str) -> str:
        from openai import AsyncOpenAI

        base_url = settings.vision_base_url or settings.openai_base_url
        client = AsyncOpenAI(
            base_url=base_url,
            api_key=settings.vision_api_key or settings.openai_api_key or "not-needed",
        )
        content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        for p in paths:
            data_uri = f"data:{self._mime(p)};base64,{self._encode(p)}"
            content.append({"type": "image_url", "image_url": {"url": data_uri}})

        resp = await client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": content}],
            temperature=0.2,
        )
        return resp.choices[0].message.content or "No analysis generated."
