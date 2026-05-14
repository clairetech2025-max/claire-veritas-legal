from __future__ import annotations

import os
from typing import Dict, List, Optional

import requests

try:
    from llama_api import LlamaClient
except Exception:  # pragma: no cover - optional fallback
    LlamaClient = None


class LocalModelClient:
    def __init__(self, api_url: Optional[str] = None, model_id: Optional[str] = None):
        self.api_url = (api_url or os.getenv("CLAIRE_API_URL") or "http://127.0.0.1:8080").rstrip("/")
        self.model_id = model_id or os.getenv("CLAIRE_MODEL_ID") or "local"
        self._client = None
        if LlamaClient is not None:
            try:
                self._client = LlamaClient(self.api_url)
            except Exception:
                self._client = None

    def health(self) -> bool:
        try:
            r = requests.get(f"{self.api_url}/v1/models", timeout=2)
            return bool(r.ok)
        except Exception:
            try:
                r = requests.get(f"{self.api_url}/health", timeout=2)
                return bool(r.ok)
            except Exception:
                return False

    def generate(self, messages: List[Dict[str, str]], *, temperature: float = 0.2, max_tokens: int = 700) -> str:
        if self._client is not None:
            try:
                return self._client.chat(messages, model=self.model_id, temperature=temperature, max_tokens=max_tokens)
            except Exception:
                pass

        payload = {"model": self.model_id, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        try:
            r = requests.post(f"{self.api_url}/v1/chat/completions", json=payload, timeout=120)
            r.raise_for_status()
            data = r.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            return (message.get("content") or choice.get("text") or "").strip()
        except Exception:
            try:
                prompt = "\n".join(msg.get("content", "") for msg in messages if msg.get("role") != "system")
                r = requests.post(
                    f"{self.api_url}/completion",
                    json={"prompt": prompt, "temperature": temperature, "n_predict": max_tokens},
                    timeout=120,
                )
                r.raise_for_status()
                data = r.json()
                choice = (data.get("choices") or [{}])[0]
                return (choice.get("text") or data.get("content") or "").strip()
            except Exception as exc:
                return f"[offline model unavailable] {exc}"


def build_legal_system_prompt() -> str:
    return (
        "You are CLAIRE // VERITAS LEGAL, a litigation intelligence workspace. "
        "Use only grounded material when possible. If the record is incomplete, say so plainly. "
        "Write like an enterprise legal analyst, not a chatbot. Cite source fragments inline with bracketed references."
    )

