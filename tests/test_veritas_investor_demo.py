from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from lxml import html

import web.app as app_module
from demo_seed import CASE_ID
from web.services.workspace import WorkspaceStore


class FakeLLM:
    def status(self):
        return {
            "connected": True,
            "model_id": "test-investor-demo-model",
            "context_size": 8192,
            "mode_policy": "test",
        }

    def generate(self, messages, **kwargs):
        joined = "\n".join(str(item.get("content", "")) for item in messages)
        assert "HP-001" in joined or "HP-002" in joined or "HP-003" in joined
        return (
            "The sample record supports the timing issue with Exhibit HP-001, Exhibit HP-002, "
            "Exhibit HP-003, Exhibit HP-004, and Exhibit HP-005. Attorney review is required."
        )


def make_client(root: Path):
    previous_store = app_module.STORE
    previous_llm = app_module.LLM
    app_module.STORE = WorkspaceStore(root)
    app_module.LLM = FakeLLM()
    client = TestClient(app_module.app)
    client._previous_store = previous_store  # type: ignore[attr-defined]
    client._previous_llm = previous_llm  # type: ignore[attr-defined]
    return client


def restore(client: TestClient) -> None:
    previous_store = getattr(client, "_previous_store", None)
    previous_llm = getattr(client, "_previous_llm", None)
    if previous_store is not None:
        app_module.STORE = previous_store
    if previous_llm is not None:
        app_module.LLM = previous_llm


def test_investor_page_removes_placeholder_demo_language():
    client = TestClient(app_module.app)
    response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert "Harbor Point Commercial Dispute" in html
    assert "ACME LAW" not in html
    assert "Plaintiff v. Defendant" not in html
    assert "courtlistener-regression-smoke" not in html
    assert "Synthetic CourtListener regression check" not in html
    assert "E:\\evidence\\matter_export" not in html
    assert "demo-evidence-count" in html
    assert "Load Demo Matter" in html


def test_mobile_action_result_panels_are_present_and_wired():
    client = TestClient(app_module.app)
    response = client.get("/")
    assert response.status_code == 200
    document = html.fromstring(response.text)
    panel_ids = {
        "demo-matter-result",
        "matter-selection-result",
        "file-ingest-result",
        "folder-ingest-result",
        "paste-ingest-result",
        "search-result",
        "chat-result",
        "timeline-result",
        "contradictions-result",
        "trace-result",
        "packet-result",
        "export-result",
        "health-result",
        "ocr-result",
        "matter-result",
        "court-rules-result",
        "docket-result",
    }
    for panel_id in panel_ids:
        nodes = document.xpath(f'//*[@id="{panel_id}"]')
        assert nodes, panel_id
        assert nodes[0].xpath('.//*[contains(@class, "action-result-body")]')
        assert "No result yet." in nodes[0].text_content()

    js = (app_module.STATIC_DIR / "app.js").read_text(encoding="utf-8")
    required_button_panels = {
        "load-demo-matter": "demo-matter-result",
        "refresh-matters": "matter-selection-result",
        "run-ingest": "file-ingest-result",
        "run-corpus": "folder-ingest-result",
        "run-paste": "paste-ingest-result",
        "run-search": "search-result",
        "run-chat": "chat-result",
        "build-timeline": "timeline-result",
        "refresh-timeline": "timeline-result",
        "find-contradictions": "contradictions-result",
        "view-trace": "trace-result",
        "refresh-trace": "trace-result",
        "run-draft": "packet-result",
        "export-draft": "export-result",
        "refresh-workspace": "health-result",
        "run-ocr": "ocr-result",
        "save-matter": "matter-result",
        "load-court-rules": "court-rules-result",
        "import-docket": "docket-result",
    }
    for button_id, panel_id in required_button_panels.items():
        assert f'"{button_id}"' in js
        assert f'"{panel_id}"' in js
    assert "Deployed SHA" in js
    assert "Build ref" in js
    assert "async function withAction" in js
    assert "button.disabled = true" in js
    assert "scrollActionPanel" in js


def test_health_marks_local_folder_import_as_public_disabled_by_default(monkeypatch):
    monkeypatch.delenv("VERITAS_LOCAL_DESKTOP_MODE", raising=False)
    client = TestClient(app_module.app)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["capabilities"]["local_folder_import"] is False
    assert payload["deployment"]["application"] == "Veritas Legal"
    assert "source_git_sha" in payload["deployment"]


def test_harbor_point_demo_matter_loads_real_workspace_paths():
    with tempfile.TemporaryDirectory() as td:
        client = make_client(Path(td))
        try:
            loaded = client.post("/demo-matter")
            assert loaded.status_code == 200
            payload = loaded.json()
            assert payload["case_id"] == CASE_ID
            assert payload["matter"]["title"] == "Harbor Point Commercial Dispute"
            assert payload["evidence_items"] >= 7
            assert payload["docket_entries"] >= 6
            assert payload["trace_id"]

            matter = client.get("/matter", params={"case_id": CASE_ID}).json()
            assert matter["matter"]["plaintiff"] == "Harbor Point Holdings, LLC"
            assert matter["matter"]["defendant"] == "North Coast Development Group, Inc."

            search = client.post(
                "/search",
                json={
                    "case_id": CASE_ID,
                    "query": "termination notice cure period expired delivery receipt",
                    "top_k": 8,
                },
            )
            assert search.status_code == 200
            hits = search.json()["items"]
            assert hits
            assert any("HP-003" in item.get("source_name", "") or "termination" in item.get("text", "").lower() for item in hits)

            timeline = client.post("/timeline", json={"case_id": CASE_ID, "limit": 40})
            assert timeline.status_code == 200
            assert len(timeline.json()["items"]) >= 6

            analysis = client.post(
                "/analyze",
                json={"case_id": CASE_ID, "query": "termination notice cure period contradiction", "top_k": 10},
            )
            assert analysis.status_code == 200
            anomalies = analysis.json()["anomalies"]
            assert any(
                "contradiction" in item["label"] or "deadline" in item["label"] or "inconsist" in item["summary"].lower()
                for item in anomalies
            )
        finally:
            restore(client)


def test_demo_grounded_chat_returns_citations_and_packet_export():
    with tempfile.TemporaryDirectory() as td:
        client = make_client(Path(td))
        try:
            assert client.post("/demo-matter").status_code == 200
            question = "What evidence supports the allegation that the termination notice was sent before the cure period expired?"
            chat = client.post(
                "/chat",
                json={"case_id": CASE_ID, "message": question, "mode": "legal", "top_k": 8},
            )
            assert chat.status_code == 200
            body = chat.json()
            assert "HP-00" in body["reply"]
            assert body["citations"]
            assert body["trace_id"]

            export = client.post(
                "/export_packet",
                json={
                    "case_id": CASE_ID,
                    "template_id": "case_theory_memo",
                    "query": question,
                    "format": "markdown",
                    "redact": True,
                },
            )
            assert export.status_code == 200
            packet = export.json()
            assert "Harbor Point Commercial Dispute" in packet["markdown"]
            assert packet["packet"]["firm_profile"]
            assert packet["packet"]["authority"]["valid"] is True
        finally:
            restore(client)
