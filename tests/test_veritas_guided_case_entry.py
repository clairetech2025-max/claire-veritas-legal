from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient
from lxml import html

import web.app as app_module
from web.services.workspace import WorkspaceStore


def make_client(root: Path) -> TestClient:
    previous_store = app_module.STORE
    app_module.STORE = WorkspaceStore(root)
    client = TestClient(app_module.app)
    client._previous_store = previous_store  # type: ignore[attr-defined]
    return client


def restore(client: TestClient) -> None:
    previous_store = getattr(client, "_previous_store", None)
    if previous_store is not None:
        app_module.STORE = previous_store


def test_guided_case_entry_routes_load_without_replacing_dashboard() -> None:
    client = TestClient(app_module.app)

    classic = client.get("/")
    assert classic.status_code == 200
    assert "Load Demo Matter" in classic.text

    for path in ("/guided", "/veritas/guided", "/?ui=guided"):
        response = client.get(path)
        assert response.status_code == 200
        assert "Guided Case Workstation" in response.text
        assert "Create New Case" in response.text
        assert "Resume Last Case" in response.text
        assert "Classic Dashboard" in response.text
        assert "/home/" not in response.text
        assert ".env" not in response.text


def test_guided_case_entry_has_required_panels_and_controls() -> None:
    client = TestClient(app_module.app)
    response = client.get("/guided")
    assert response.status_code == 200

    document = html.fromstring(response.text)
    required_ids = {
        "entry-screen",
        "intake-screen",
        "review-screen",
        "active-screen",
        "entry-result",
        "intake-result",
        "review-result",
        "active-result",
        "create-new-case",
        "resume-last-case",
        "choose-another-case",
        "open-existing-case",
        "guided-answer",
        "intake-continue",
        "intake-back",
        "intake-skip",
        "create-case-final",
        "active-add-documents",
        "active-change-case",
    }

    for element_id in required_ids:
        nodes = document.xpath(f'//*[@id="{element_id}"]')
        assert nodes, element_id

    for panel_id in ("entry-result", "intake-result", "review-result", "active-result"):
        panel = document.xpath(f'//*[@id="{panel_id}"]')[0]
        assert panel.xpath('.//*[contains(@class, "action-result-body")]')
        assert "No result yet." in panel.text_content()


def test_guided_case_create_uses_real_matter_persistence() -> None:
    with tempfile.TemporaryDirectory() as td:
        client = make_client(Path(td))
        try:
            response = client.post(
                "/matter",
                json={
                    "case_id": "guided-mobile-test",
                    "case_number": "Not assigned yet",
                    "title": "Guided Mobile Test",
                    "court_name": "United States District Court",
                    "jurisdiction": "Federal",
                    "matter_type": "Commercial Litigation",
                    "practice_area": "Commercial Litigation",
                    "plaintiff": "Harbor Point Holdings, LLC",
                    "defendant": "North Coast Development Group, Inc.",
                    "current_status": "Intake",
                    "notes": "Optional details remain editable after creation.",
                },
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload["ok"] is True
            assert payload["matter"]["case_number"] == "Not assigned yet"
            assert payload["matter"]["current_status"] == "Intake"

            matter = client.get("/matter", params={"case_id": "guided-mobile-test"})
            assert matter.status_code == 200
            matter_record = matter.json()["matter"]
            assert matter_record["title"] == "Guided Mobile Test"
            assert matter_record["case_number"] == "Not assigned yet"
            assert matter_record["current_status"] == "Intake"

            cases = client.get("/cases")
            assert cases.status_code == 200
            case = next(item for item in cases.json()["items"] if item["case_id"] == "guided-mobile-test")
            assert case["title"] == "Guided Mobile Test"
            assert case["status"] == "Intake"
        finally:
            restore(client)


def test_guided_javascript_uses_shared_action_state_contract() -> None:
    js = (app_module.STATIC_DIR / "guided.js").read_text(encoding="utf-8")
    assert "async function withAction" in js
    assert "setActionPanel(panelId, \"loading\"" in js
    assert "button.disabled = true" in js
    assert "scrollActionPanel(panelId)" in js
    assert "localStorage.setItem(STORAGE_KEY" in js
    assert "guidedStateAction(event.currentTarget" in js
    assert "appeal_number" in js
    assert "administrative_number" in js
    assert "Document workflow is the next milestone" in js
    assert "This active-case tool is reserved for a later milestone" in js
