from __future__ import annotations

from fastapi.testclient import TestClient

from web.app import app


def test_dark_veritas_shell_exposes_claire_front_door():
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert "Case Preparation Workspace" in html
    assert "->" not in html
    assert "CLAIRE Legal Assistant" in html
    assert "Ask Claire" in html
    assert "Advanced Dashboard" in html
    assert "Work the case in court order" not in html
    assert "Your question (press Enter to ask)" in html
    assert "front-door-input" in html
    assert "front-door-go" in html
    assert "New Matter" in html
    assert "Upload Evidence" in html
    assert "Legal Research" in html
    assert "Draft Report" in html


def test_advanced_dashboard_remains_available():
    client = TestClient(app)
    response = client.get("/dashboard")

    assert response.status_code == 200
    html = response.text
    assert "VERITAS LEGAL" in html
    assert "Integrated Surface" in html
    assert "System Status" in html
    for jargon in ("Front Door Routing", "Recognition Rail", "Workflow Spine", "visor", "Ex Tenebris"):
        assert jargon not in html, jargon
