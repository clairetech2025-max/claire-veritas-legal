#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

import web.app as web_app
import web.services.llm as llm_module
from web.services.llm import LocalModelClient
from web.services.workspace import WorkspaceStore


ROOT = Path(__file__).resolve().parent


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_public_files() -> None:
    required = [
        "README.md",
        "SELLABLE_PACKAGE.md",
        "requirements-web.txt",
        "web/app.py",
        "web/index.html",
        "web/static/app.js",
        "web/static/styles.css",
        "demo_seed.py",
    ]
    for relpath in required:
        assert_true((ROOT / relpath).exists(), f"missing {relpath}")


def check_ignored_private_paths() -> None:
    ignored = subprocess.run(
        ["git", "check-ignore", "memory/", "vault/", ".claire_veritas/", ".env.local"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = set(ignored.stdout.splitlines())
    for relpath in {"memory/", "vault/", ".claire_veritas/", ".env.local"}:
        assert_true(relpath in output, f"{relpath} is not ignored")


def check_workspace_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "web" / "rules").mkdir(parents=True)
        for profile in (ROOT / "web" / "rules").glob("*.json"):
            (root / "web" / "rules" / profile.name).write_text(profile.read_text(encoding="utf-8"), encoding="utf-8")
        store = WorkspaceStore(root)
        matter = store.upsert_matter(
            {
                "case_id": "smoke-demo",
                "title": "Smoke Demo Matter",
                "court_profile_id": "federal_district_civil",
                "confidentiality_level": "Synthetic",
                "notes": "Synthetic smoke test matter.",
            }
        )
        result = store.ingest_text(
            "Exhibit A. The service notice identifies an elevator outage and alternate routing.",
            case_id="smoke-demo",
            case_title=matter["title"],
            source_type="demo_exhibit",
            file_name="exhibit-a.txt",
            mime_type="text/plain",
            metadata={"synthetic": True},
        )
        hits = store.search("elevator outage alternate routing", case_id="smoke-demo", top_k=3)
        assert_true(result.get("chunks", 0) >= 1, "ingest wrote no chunks")
        assert_true(bool(hits), "search returned no hits")
        assert_true(hits[0].get("case_id") == "smoke-demo", "search hit case mismatch")


def check_chat_fallback_when_model_blank() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "web" / "rules").mkdir(parents=True)
        for profile in (ROOT / "web" / "rules").glob("*.json"):
            (root / "web" / "rules" / profile.name).write_text(profile.read_text(encoding="utf-8"), encoding="utf-8")
        original_store = web_app.STORE
        original_generate = web_app.LLM.generate
        web_app.STORE = WorkspaceStore(root)
        web_app.STORE.upsert_matter({"case_id": "smoke-demo", "title": "Smoke Demo Matter"})
        web_app.STORE.ingest_text(
            "Exhibit A. Elevator outage notice listed alternate routing but no accessible shuttle coverage.",
            case_id="smoke-demo",
            case_title="Smoke Demo Matter",
            source_type="demo_exhibit",
            file_name="exhibit-a.txt",
            mime_type="text/plain",
            metadata={"synthetic": True},
        )
        web_app.STORE.append_trace(
            {
                "case_id": "smoke-demo",
                "event_type": "chat",
                "title": "elevator outage alternate routing",
                "summary": "The grounded record has matching material, but the local model returned no draft.",
                "metadata": {"synthetic": True},
            }
        )
        web_app.LLM.generate = lambda *args, **kwargs: ""
        try:
            client = TestClient(web_app.app)
            response = client.post(
                "/chat",
                json={"message": "elevator outage alternate routing", "case_id": "smoke-demo", "mode": "legal", "top_k": 3},
            )
            assert_true(response.status_code == 200, f"chat returned {response.status_code}")
            payload = response.json()
            reply = payload.get("reply") or ""
            assert_true("local model returned no draft" in reply, "blank model fallback did not run")
            assert_true("Elevator outage" in reply or "elevator outage" in reply, "fallback did not cite grounded evidence")
            assert_true(reply.count("local model returned no draft") == 1, "fallback echoed prior chat trace")
        finally:
            web_app.STORE = original_store
            web_app.LLM.generate = original_generate


def check_llm_accepts_bridge_response_shape() -> None:
    class FakeResponse:
        ok = True

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"ok": True, "response": "Bridge response text", "source": "go"}

    original_post = llm_module.requests.post
    original_get = llm_module.requests.get
    llm_module.requests.post = lambda *args, **kwargs: FakeResponse()
    llm_module.requests.get = lambda *args, **kwargs: FakeResponse()
    try:
        client = LocalModelClient(api_url="http://127.0.0.1:8080", model_id="local")
        assert_true(
            client.generate([{"role": "user", "content": "test"}]) == "Bridge response text",
            "LLM client did not accept bridge response field",
        )
    finally:
        llm_module.requests.post = original_post
        llm_module.requests.get = original_get


def main() -> int:
    check_public_files()
    check_ignored_private_paths()
    check_workspace_roundtrip()
    check_chat_fallback_when_model_blank()
    check_llm_accepts_bridge_response_shape()
    print("smoke_test: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
