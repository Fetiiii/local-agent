from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

import requests


class ModelClient:
    """Client for llama.cpp compatible chat completions."""

    def __init__(self, base_url: str = "http://127.0.0.1:8080") -> None:
        self.base_url = base_url.rstrip("/")
        self.active_mode = "default"
        self.mode_params: Dict[str, Any] = {}

    def set_mode(self, mode: str) -> None:
        self.active_mode = mode

    def update_params(self, params: Dict[str, Any]) -> None:
        # Replace the current params with the new mode's params to avoid cross-mode leakage.
        self.mode_params = dict(params)

    def health_check(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/", timeout=5)
            return resp.ok
        except Exception:
            return False

    def _clean_llm_output(self, text: str) -> str:
        """Strip meta tags, channel markers, odd prefixes, and fix double-escaped unicode."""
        if not text:
            return ""

        # Remove analysis/assistantfinal chatter
        text = re.sub(r"analysis.*?assistantfinal", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = text.replace("assistantfinal", "")
        text = text.replace("assistant final", "")
        text = text.replace("analysis", "")

        # Remove common meta markers
        text = re.sub(r"<\|analysis\|>.*?<\|message\|>", "", text, flags=re.DOTALL)
        text = re.sub(r"<\|.*?\|>", "", text)
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)

        # Drop JSON prefix if present
        if re.match(r"^\{.*?\}", text, flags=re.DOTALL):
            text = re.sub(r"^\{.*?\}", "", text, flags=re.DOTALL)

        # Clip from first likely start
        for anchor in ["Merhaba", "Selam", "Hello", "Hi", "Ü", "İ", "Ç", "Ş", "Ğ", "Ö"]:
            idx = text.find(anchor)
            if idx != -1:
                text = text[idx:]
                break

        # Unescape sequences
        text = text.replace("\\n", "\n").replace("\\r", "")
        text = text.replace('\\"', '"')
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]

        # Decode unicode escapes and fix double-encoded UTF-8
        try:
            unescaped = text.encode("utf-8").decode("unicode_escape")
            text = unescaped.encode("latin-1", errors="ignore").decode("utf-8", errors="ignore")
        except Exception:
            pass

        text = text.replace("\r", "")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def generate(
        self,
        messages: List[Dict[str, Any]],
        mode: Optional[str] = None,
        stream: bool = False,
        timeout: int = 300,
    ) -> str:
        payload = self._build_payload(messages, mode or self.active_mode)
        payload["stream"] = stream

        try:
            resp = requests.post(
                f"{self.base_url}/v1/chat/completions",
                json=payload,
                timeout=timeout,
                stream=stream,
            )
            resp.raise_for_status()

            if stream:
                collected = []
                for raw_chunk in resp.iter_lines(decode_unicode=True):
                    if not raw_chunk:
                        continue
                    if raw_chunk.startswith("data: "):
                        raw_chunk = raw_chunk[6:]
                    try:
                        j = json.loads(raw_chunk)
                        delta = j["choices"][0]["delta"].get("content", "")
                        collected.append(delta)
                    except Exception:
                        continue
                final = "".join(collected)
                return self._clean_llm_output(final)

            data = resp.json()
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                return self._clean_llm_output(content)
            return str(data)

        except Exception as e:
            return f"[LLM Hatası: {e}]"

    def _build_payload(self, messages: List[Dict[str, Any]], mode: str) -> Dict[str, Any]:
        """
        Build the llama.cpp chat-completions payload.
        - Inject the mode's system prompt as the first message so the model behaves consistently.
        - Carry over tuning params (ctx size, stop, penalties).
        """
        max_tokens = self.mode_params.get("max_tokens", 4096)
        temperature = self.mode_params.get("temperature", 0.7)

        # Always start with an explicit system prompt if provided by the mode config.
        final_messages: List[Dict[str, Any]] = []
        system_prompt = self.mode_params.get("system_prompt")
        if system_prompt:
            final_messages.append({"role": "system", "content": system_prompt})
        final_messages.extend(messages)

        payload: Dict[str, Any] = {
            "mode": mode,
            "messages": final_messages,
            "max_tokens": max_tokens,
            "n_predict": max_tokens,
            "temperature": temperature,
            "top_p": self.mode_params.get("top_p", 0.9),
            "min_p": self.mode_params.get("min_p", 0.05),
            "repeat_penalty": self.mode_params.get("repeat_penalty", 1.1),
        }
        if "context_size" in self.mode_params:
            payload["ctx_size"] = self.mode_params["context_size"]
        if "stop" in self.mode_params:
            payload["stop"] = self.mode_params["stop"]
        return payload
