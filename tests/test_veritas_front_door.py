from __future__ import annotations

from fastapi.testclient import TestClient

from web.app import app


def test_dark_veritas_shell_exposes_claire_front_door():
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert "CLAIRE Front Door" in html
    assert "What are we working on today?" in html
    assert "front-door-input" in html
    assert "front-door-go" in html
    assert "New Matter" in html
    assert "Upload Evidence" in html
    assert "Research Citation" in html
    assert "Draft Report" in html
