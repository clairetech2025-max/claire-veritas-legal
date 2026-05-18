from __future__ import annotations

import os
from pathlib import Path
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

    def _project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    def _search_roots(self) -> List[Path]:
        roots = [self._project_root()]
        env_root = os.getenv("CLAIRE_LLAMA_ROOT")
        if env_root:
            roots.append(Path(env_root))
        roots.extend(
            [
                Path(r"I:\Claire_new"),
                Path(r"I:\ClaireTech"),
            ]
        )
        seen = set()
        resolved: List[Path] = []
        for root in roots:
            key = str(root).lower()
            if key in seen or not root.exists():
                continue
            seen.add(key)
            resolved.append(root)
        return resolved

    def _find_model_path(self) -> Optional[Path]:
        preferred: List[Path] = [
            self._project_root() / "models",
            self._project_root() / "integrations" / "llama" / "models",
            Path(r"I:\Claire_new\models"),
            Path(r"I:\Claire_new\integrations\llama\models"),
            Path(r"I:\ClaireTech\models"),
            Path(r"I:\ClaireTech\integrations\llama\models"),
        ]
        candidates: List[Path] = []
        for root in preferred:
            if root.exists():
                candidates.extend(root.rglob("*.gguf"))
        if candidates:
            candidates = sorted(
                candidates,
                key=lambda path: (path.stat().st_size if path.exists() else 0, path.stat().st_mtime if path.exists() else 0),
                reverse=True,
            )
            return candidates[0]
        for root in self._search_roots():
            candidates.extend(root.rglob("*.gguf"))
        candidates = sorted(
            candidates,
            key=lambda path: (path.stat().st_size if path.exists() else 0, path.stat().st_mtime if path.exists() else 0),
            reverse=True,
        )
        return candidates[0] if candidates else None

    def _find_server_path(self) -> Optional[Path]:
        roots = self._search_roots()
        preferred: List[Path] = []
        for root in roots:
            preferred.extend(
                [
                    root / "integrations" / "llama" / "llama-server.exe",
                    root / "llama" / "llama-server.exe",
                    root / "llama-server.exe",
                ]
            )
        for candidate in preferred:
            if candidate.exists():
                return candidate
        candidates: List[Path] = []
        for root in roots:
            candidates.extend(root.rglob("llama-server.exe"))
        candidates = sorted(candidates)
        return candidates[0] if candidates else None

    def _discover_server_model_id(self) -> Optional[str]:
        try:
            r = requests.get(f"{self.api_url}/v1/models", timeout=3)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return None
        for item in data.get("data") or []:
            model_id = item.get("id")
            if model_id:
                return str(model_id)
        for item in data.get("models") or []:
            model_id = item.get("id") or item.get("model") or item.get("name")
            if model_id:
                return str(model_id)
        return None

    def _effective_model_id(self) -> str:
        configured = (self.model_id or "").strip()
        if configured and configured.lower() != "local":
            return configured
        discovered = self._discover_server_model_id()
        return discovered or configured or "local"

    def status(self) -> Dict[str, object]:
        model_path = self._find_model_path()
        server_path = self._find_server_path()
        connected = False
        reason = "offline"
        effective_model_id = self.model_id
        try:
            r = requests.get(f"{self.api_url}/v1/models", timeout=2)
            connected = bool(r.ok)
            if connected:
                effective_model_id = self._effective_model_id()
        except Exception:
            try:
                r = requests.get(f"{self.api_url}/health", timeout=2)
                connected = bool(r.ok)
            except Exception:
                connected = False

        if connected:
            reason = "connected"
        elif server_path is None and model_path is None:
            reason = "missing_server_and_model"
        elif server_path is None:
            reason = "missing_server"
        elif model_path is None:
            reason = "missing_model"
        else:
            reason = "service_offline"

        return {
            "api_url": self.api_url,
            "model_id": effective_model_id,
            "connected": connected,
            "reason": reason,
            "server_path": str(server_path) if server_path else None,
            "model_path": str(model_path) if model_path else None,
        }

    def health(self) -> bool:
        return bool(self.status().get("connected"))

    def generate(self, messages: List[Dict[str, str]], *, temperature: float = 0.2, max_tokens: int = 700) -> str:
        model_id = self._effective_model_id()
        if self._client is not None:
            try:
                return self._client.chat(messages, model=model_id, temperature=temperature, max_tokens=max_tokens)
            except Exception:
                pass

        payload = {"model": model_id, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
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


def normalize_chat_mode(mode: Optional[str]) -> str:
    return "creator" if str(mode or "").strip().lower() == "creator" else "legal"


def build_chat_mode_context(mode: Optional[str] = None) -> str:
    if normalize_chat_mode(mode) != "creator":
        return ""
    return (
        "House orientation:\n"
        "- Steven Roth is the creator and lead architect of Claire Systems.\n"
        "- Lucius Prime is an in-house creator identity tied to Steven Roth.\n"
        "- Cody is the build and stabilization copilot reserved for startup, workflow, and systems work.\n"
        "- Treat this house context as creator metadata, not as grounded legal evidence."
    )


def build_legal_system_prompt(mode: Optional[str] = None) -> str:
    normalized = normalize_chat_mode(mode)
    base = (
        "You are CLAIRE // VERITAS LEGAL, a litigation intelligence workspace. "
        "Use only grounded material when possible. If the record is incomplete, say so plainly. "
        "Write like an enterprise legal analyst, not a chatbot. Cite source fragments inline with bracketed references."
    )
    if normalized == "creator":
        return (
            f"{base} "
            "Creator Mode is active. You may answer creator and house-orientation questions directly from the provided house context, "
            "but you must distinguish that house context from grounded legal evidence."
        )
    return base

