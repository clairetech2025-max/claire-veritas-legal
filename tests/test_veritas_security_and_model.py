from __future__ import annotations

from fastapi.testclient import TestClient

import web.app as app_module
import web.services.llm as llm_module
from web.services.llm import LocalModelClient


def test_access_password_secret_gates_case_workspace(monkeypatch):
    monkeypatch.setenv("VERITAS_ACCESS_PASSWORD", "firm-passphrase")
    monkeypatch.setenv("VERITAS_SESSION_SECRET", "test-session-secret")
    client = TestClient(app_module.app)

    blocked_page = client.get("/", follow_redirects=False)
    assert blocked_page.status_code in {302, 303, 307}
    assert blocked_page.headers["location"].endswith("/login")

    blocked_api = client.post("/chat", json={"message": "What is in this matter?"})
    assert blocked_api.status_code == 401
    assert blocked_api.json()["detail"] == "Login required."

    failed_login = client.post("/login", data={"password": "wrong"}, follow_redirects=False)
    assert failed_login.status_code == 401

    login = client.post("/login", data={"password": "firm-passphrase"}, follow_redirects=False)
    assert login.status_code in {302, 303}
    assert "veritas_session" in login.headers.get("set-cookie", "")

    allowed = client.get("/")
    assert allowed.status_code == 200
    assert "CLAIRE Front Door" in allowed.text


def test_model_connector_uses_private_bearer_secret(monkeypatch):
    calls: list[tuple[str, dict[str, str] | None]] = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, *, timeout=None, headers=None):
        calls.append((url, headers))
        return FakeResponse({"data": [{"id": "private-legal-model"}]})

    def fake_post(url, *, json=None, timeout=None, headers=None):
        calls.append((url, headers))
        return FakeResponse({"choices": [{"message": {"content": "grounded answer"}}]})

    monkeypatch.setenv("CLAIRE_API_URL", "https://private-model.example")
    monkeypatch.setenv("CLAIRE_MODEL_API_KEY", "secret-model-token")
    monkeypatch.setenv("CLAIRE_MODEL_ID", "private-legal-model")
    monkeypatch.setattr(llm_module.requests, "get", fake_get)
    monkeypatch.setattr(llm_module.requests, "post", fake_post)

    client = LocalModelClient()
    assert client.status()["connected"] is True
    reply = client.generate([{"role": "user", "content": "Summarize the record."}])

    assert reply == "grounded answer"
    assert calls
    assert all(headers and headers.get("Authorization") == "Bearer secret-model-token" for _, headers in calls)


def test_model_connector_can_use_claire_runtime_reply_endpoint(monkeypatch):
    calls: list[tuple[str, dict | None]] = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, *, timeout=None, headers=None):
        calls.append((url, None))
        return FakeResponse({"are": "ONLINE", "llm": "READY", "build": "PRIVATE_FULL"})

    def fake_post(url, *, json=None, timeout=None, headers=None):
        calls.append((url, json))
        return FakeResponse({"source": "CLAIRE", "reply": "Claire runtime grounded response."})

    monkeypatch.setenv("CLAIRE_RUNTIME_URL", "https://claire-runtime.example")
    monkeypatch.delenv("CLAIRE_API_URL", raising=False)
    monkeypatch.delenv("CLAIRE_MODEL_API_URL", raising=False)
    monkeypatch.setattr(llm_module.requests, "get", fake_get)
    monkeypatch.setattr(llm_module.requests, "post", fake_post)

    client = LocalModelClient()
    status = client.status()
    reply = client.generate([{"role": "user", "content": "Review this matter."}])

    assert status["connected"] is True
    assert status["reason"] == "claire_runtime_connected"
    assert status["model_id"] == "claire-runtime"
    assert reply == "Claire runtime grounded response."
    assert any(url == "https://claire-runtime.example/status" for url, _ in calls)
    assert any(url == "https://claire-runtime.example/reply" and payload == {"q": "Review this matter."} for url, payload in calls)


def test_model_connector_uses_claire_are_v1_complete_endpoint(monkeypatch):
    calls: list[tuple[str, dict | None]] = []

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    def fake_get(url, *, timeout=None, headers=None):
        calls.append((url, None))
        if url.endswith("/v1/health"):
            return FakeResponse({"status": "ok", "root": "/tmp/claire", "records": 3})
        return FakeResponse({"status": "not_found"})

    def fake_post(url, *, json=None, timeout=None, headers=None):
        calls.append((url, json))
        return FakeResponse(
            {
                "prompt": json["prompt"],
                "lane": json["lane"],
                "model": json["model"],
                "recall_event_sha": "recall-sha",
                "completion_event_sha": "completion-sha",
                "memories_used": [],
                "answer": "CLAIRE ARE governed legal answer.",
            }
        )

    monkeypatch.setenv("CLAIRE_RUNTIME_URL", "https://claire-are.example")
    monkeypatch.setattr(llm_module.requests, "get", fake_get)
    monkeypatch.setattr(llm_module.requests, "post", fake_post)

    client = LocalModelClient()
    status = client.status()
    reply = client.generate([{"role": "user", "content": "Find evidence gaps."}])

    assert status["connected"] is True
    assert status["reason"] == "claire_are_connected"
    assert status["model_id"] == "claire-are"
    assert reply == "CLAIRE ARE governed legal answer."
    assert ("https://claire-are.example/v1/health", None) in calls
    assert any(
        url == "https://claire-are.example/v1/llm/complete"
        and payload == {
            "prompt": "Find evidence gaps.",
            "lane": "legal",
            "model": "veritas-legal",
            "metadata": {"caller": "veritas_legal"},
        }
        for url, payload in calls
    )
