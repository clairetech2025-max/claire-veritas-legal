from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

import web.app as app_module
from web.services.public_web import expand_public_web_query, parse_duckduckgo_html
from web.services.workspace import WorkspaceStore


class EmptyCourtListener:
    def search(self, *args, **kwargs):
        return {"count": 0, "results": [], "warnings": []}


class EmptyCaliforniaRegulations:
    def lookup(self, query: str):
        return {"used": False, "reason": "no_public_regulation_match", "results": [], "count": 0}


class FakePublicWeb:
    def search(self, query: str, *, max_results: int = 4):
        return {
            "used": True,
            "reason": "public_web_search",
            "query": query,
            "count": 1,
            "results": [
                {
                    "title": "Cal. Code Regs. Tit. 14, § 4331 - Soliciting",
                    "snippet": "No person shall solicit, sell, hawk, or peddle any goods, wares, merchandise, liquids, or edibles for human consumption.",
                    "source_url": "https://www.law.cornell.edu/regulations/california/14-CCR-4331",
                    "citation": "14 CCR § 4331",
                    "text": "No person shall solicit, sell, hawk, or peddle any goods.",
                }
            ],
        }


def test_public_web_parser_extracts_duckduckgo_results():
    html = """
    <div class="result">
      <h2 class="result__title">
        <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fsource">Example &amp; Source</a>
      </h2>
      <a class="result__snippet">Snippet with <b>markup</b>.</a>
    </div></div>
    """
    results = parse_duckduckgo_html(html)
    assert results[0]["title"] == "Example & Source"
    assert results[0]["source_url"] == "https://example.com/source"
    assert results[0]["snippet"] == "Snippet with markup ."


def test_public_web_expands_ccr_shorthand_queries():
    queries = expand_public_web_query("CCR-4331")
    assert "CCR 4331 California Code of Regulations" in queries
    assert "14 CCR 4331" in queries


def test_public_web_routing_is_default_except_evidence_only_queries():
    assert app_module._should_use_public_web("CCR-4331", {"matches": True}) is True
    assert app_module._should_use_public_web("what is CCR-4331", {"matches": False}) is True
    assert app_module._should_use_public_web("summarize this matter in the evidence", {"matches": True}) is False


def test_chat_uses_public_web_for_ccr_when_local_evidence_is_empty(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        previous_store = app_module.STORE
        previous_courtlistener = app_module.COURTLISTENER
        previous_public_web = app_module.PUBLIC_WEB
        previous_calregs = app_module.CALIFORNIA_REGULATIONS
        app_module.STORE = WorkspaceStore(Path(td))
        app_module.COURTLISTENER = EmptyCourtListener()
        app_module.PUBLIC_WEB = FakePublicWeb()
        app_module.CALIFORNIA_REGULATIONS = EmptyCaliforniaRegulations()
        client = TestClient(app_module.app)
        try:
            response = client.post("/chat", json={"message": "CCR-4331", "mode": "legal"})
            assert response.status_code == 200
            payload = response.json()
            assert payload["public_web_search"]["used"] is True
            assert "Cal. Code Regs. Tit. 14" in payload["reply"]
            assert "record does not contain" not in payload["reply"].lower()
            assert payload["citations"] == []
        finally:
            app_module.STORE = previous_store
            app_module.COURTLISTENER = previous_courtlistener
            app_module.PUBLIC_WEB = previous_public_web
            app_module.CALIFORNIA_REGULATIONS = previous_calregs
