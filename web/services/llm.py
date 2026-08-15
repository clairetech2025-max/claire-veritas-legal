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
        claire_root = Path.home() / "claire"
        roots = [self._project_root(), claire_root]
        env_root = os.getenv("CLAIRE_LLAMA_ROOT")
        if env_root:
            roots.append(Path(env_root))
        roots.extend(
            [
                claire_root / "models",
                claire_root / "llama.cpp",
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
            Path.home() / "claire" / "models",
            Path.home() / "claire" / "llama.cpp" / "models",
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

    def _find_model_path_by_name(self, model_name: str) -> Optional[Path]:
        wanted = Path(str(model_name or "")).name
        if not wanted:
            return None
        for root in self._search_roots():
            try:
                for candidate in root.rglob(wanted):
                    if candidate.is_file():
                        return candidate
            except Exception:
                continue
        return None

    def _find_server_path(self) -> Optional[Path]:
        roots = self._search_roots()
        preferred: List[Path] = []
        for root in roots:
            preferred.extend(
                [
                    root / "llama.cpp" / "build" / "bin" / "llama-server",
                    root / "build" / "bin" / "llama-server",
                    root / "llama-server",
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
            candidates.extend(root.rglob("llama-server"))
            candidates.extend(root.rglob("llama-server.exe"))
        candidates = sorted(candidates)
        return candidates[0] if candidates else None

    def _candidate_api_urls(self) -> List[str]:
        urls = [
            self.api_url,
            os.getenv("CLAIRE_VERITAS_MODEL_URL") or "",
            os.getenv("CLAIRE_MODEL_API_URL") or "",
            "http://127.0.0.1:8091",
            "http://127.0.0.1:8081",
            "http://127.0.0.1:8080",
        ]
        seen = set()
        result: List[str] = []
        for url in urls:
            clean = str(url or "").strip().rstrip("/")
            if not clean or clean in seen:
                continue
            seen.add(clean)
            result.append(clean)
        return result

    def _models_payload(self, api_url: str) -> Optional[Dict[str, object]]:
        try:
            r = requests.get(f"{api_url}/v1/models", timeout=2)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return None
        if data.get("data") or data.get("models") or data.get("response") or data.get("content"):
            return data
        return None

    def _active_api_url(self) -> Optional[str]:
        for api_url in self._candidate_api_urls():
            if self._models_payload(api_url):
                return api_url
        return None

    def _discover_server_model_id(self, api_url: Optional[str] = None) -> Optional[str]:
        api_url = (api_url or self._active_api_url() or self.api_url).rstrip("/")
        try:
            r = requests.get(f"{api_url}/v1/models", timeout=3)
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

    def _effective_model_id(self, api_url: Optional[str] = None) -> str:
        configured = (self.model_id or "").strip()
        if configured and configured.lower() != "local":
            return configured
        discovered = self._discover_server_model_id(api_url)
        return discovered or configured or "local"

    def status(self) -> Dict[str, object]:
        model_path = self._find_model_path()
        server_path = self._find_server_path()
        connected = False
        reason = "offline"
        effective_model_id = self.model_id
        active_api_url = self._active_api_url()
        if active_api_url:
            connected = True
            effective_model_id = self._effective_model_id(active_api_url)
            model_path = self._find_model_path_by_name(effective_model_id) or model_path

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
            "api_url": active_api_url or self.api_url,
            "model_id": effective_model_id,
            "connected": connected,
            "reason": reason,
            "server_path": str(server_path) if server_path else None,
            "model_path": str(model_path) if model_path else None,
            "context_size": int(os.getenv("VERITAS_CONTEXT_SIZE", "8192") or 8192),
            "mode_policy": "adaptive: non-thinking for summaries/retrieval; thinking for legal analysis, contradictions, timelines, argument review, and evidence synthesis",
        }

    def health(self) -> bool:
        return bool(self.status().get("connected"))

    def _request_timeout(self) -> int:
        try:
            return max(30, int(os.getenv("VERITAS_MODEL_TIMEOUT", "240") or 240))
        except ValueError:
            return 240

    def generate(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int = 700,
        thinking_enabled: bool = False,
    ) -> str:
        status = self.status()
        if not status.get("connected"):
            return deterministic_legal_stub(messages, reason=str(status.get("reason") or "model_unavailable"))
        active_api_url = str(status.get("api_url") or self.api_url).rstrip("/")
        model_id = self._effective_model_id(active_api_url)

        payload = {
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": bool(thinking_enabled)},
        }
        try:
            r = requests.post(f"{active_api_url}/v1/chat/completions", json=payload, timeout=self._request_timeout())
            r.raise_for_status()
            data = r.json()
            if data.get("ok") is False:
                raise RuntimeError(str(data.get("response") or "chat completion failed"))
            direct = (data.get("response") or data.get("content") or "").strip()
            if direct:
                return direct
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            visible = (message.get("content") or choice.get("text") or "").strip()
            if visible:
                return visible
            if not thinking_enabled:
                return ""
            synthesis_messages = list(messages) + [
                {
                    "role": "system",
                    "content": "Produce the final user-visible answer only. Do not reveal hidden reasoning. Keep citations and uncertainty labels explicit.",
                }
            ]
            synthesis_payload = {
                "model": model_id,
                "messages": synthesis_messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "chat_template_kwargs": {"enable_thinking": False},
            }
            r = requests.post(f"{active_api_url}/v1/chat/completions", json=synthesis_payload, timeout=self._request_timeout())
            r.raise_for_status()
            data = r.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            return (message.get("content") or choice.get("text") or "").strip()
        except Exception:
            try:
                prompt = "\n\n".join(f"{msg.get('role', 'user').upper()}:\n{msg.get('content', '')}" for msg in messages)
                r = requests.post(
                    f"{active_api_url}/completion",
                    json={"prompt": prompt, "temperature": temperature, "n_predict": max_tokens},
                    timeout=120,
                )
                r.raise_for_status()
                data = r.json()
                direct = (data.get("response") or data.get("content") or "").strip()
                if direct:
                    return direct
                choice = (data.get("choices") or [{}])[0]
                return (choice.get("text") or "").strip()
            except Exception as exc:
                return deterministic_legal_stub(messages, reason=f"model_request_failed:{exc}")


def _last_user_message(messages: List[Dict[str, str]]) -> str:
    for message in reversed(messages or []):
        if message.get("role") == "user":
            return str(message.get("content") or "")
    return ""


def _grounded_record_text(messages: List[Dict[str, str]]) -> str:
    for message in messages or []:
        content = str(message.get("content") or "")
        if content.startswith("Grounded record bundle:"):
            return content
    return ""


def deterministic_legal_stub(messages: List[Dict[str, str]], *, reason: str = "model_unavailable") -> str:
    """Explicit offline fallback for smoke tests and disconnected local models.

    This is not an LLM and does not pretend to search law. It keeps Veritas Legal
    usable enough to verify routing, grounding boundaries, traces, and refusal
    behavior when the local model bridge is absent.
    """
    query = _last_user_message(messages)
    lowered = query.lower()
    grounded = _grounded_record_text(messages)
    header = f"[deterministic legal stub: {reason}]"

    if "guarantee" in lowered and "win" in lowered:
        return (
            f"{header}\n"
            "I cannot guarantee a case outcome. I can identify issues, evidence gaps, risk points, and attorney-review questions from the available record."
        )

    if "wilson" in lowered and "cook" in lowered:
        if "wilson" not in grounded.lower() and "cook" not in grounded.lower():
            return (
                f"{header}\n"
                "Source support not found in the local grounded record. I will not invent citation text or claim that Wilson v. Cook supports the proposition without a source in the corpus."
            )

    if "memo" in lowered or "draft" in lowered:
        facts = "No grounded facts were found." if "[no matching grounded material]" in grounded else "Grounded facts are limited to the cited local record bundle."
        return (
            f"{header}\n"
            "Issue: Identify the legal or procedural question raised by the available record.\n"
            f"Facts used: {facts}\n"
            "Analysis: The record is incomplete, so this draft stays at issue-framing level and does not state a final legal conclusion.\n"
            "Missing evidence: governing text, enforceable record excerpts, procedural posture, and source citations.\n"
            "Next steps: add source documents, verify citations, and have counsel review before relying on any filing language."
        )

    if "regulation" in lowered and ("beyond its text" in lowered or "enforced beyond" in lowered):
        return (
            f"{header}\n"
            "Issue: Whether enforcement has exceeded the regulation's text or fair notice boundary. "
            "Without a source corpus, I cannot cite controlling authority or confirm the governing rule. "
            "The safe framing is an overbreadth/fair-notice/enforcement-authority issue for attorney review."
        )

    return (
        f"{header}\n"
        "No local model draft is attached. I can only provide bounded issue framing from grounded records and must not invent authorities, facts, or legal conclusions."
    )


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
        "Write like an enterprise legal analyst, not a chatbot. Cite source fragments inline with bracketed references. "
        "Do not provide legal advice, filing instructions, or final liability conclusions. "
        "Frame conclusions as evidence support, apparent issues, risk indicators, or questions for attorney review. "
        "Never invent authorities, quotations, dates, docket facts, parties, or document contents. "
        "Keep retrieved sources and citations separate from generated analysis. "
        "Distinguish document-supported facts, user allegations, legal analysis, and unresolved uncertainty."
    )
    if normalized == "creator":
        return (
            f"{base} "
            "Creator Mode is active. You may answer creator and house-orientation questions directly from the provided house context, "
            "but you must distinguish that house context from grounded legal evidence."
        )
    return base
