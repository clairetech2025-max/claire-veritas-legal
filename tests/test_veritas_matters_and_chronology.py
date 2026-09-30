import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

import web.app as app_module
from demo_seed import CASE_ID, seed_harbor_point_demo
from web.services.chronology import dated_events
from web.services.workspace import WorkspaceStore


def _client(root: Path) -> TestClient:
    app_module.STORE = WorkspaceStore(root)
    return TestClient(app_module.app)


def test_new_matters_with_the_same_name_never_merge():
    previous = app_module.STORE
    try:
        client = _client(Path(tempfile.mkdtemp()))
        first = client.post("/matter", json={"title": "Smith v. Jones", "plaintiff": "Ann Smith", "create": True}).json()["matter"]
        second = client.post("/matter", json={"title": "Smith v. Jones", "plaintiff": "Carl Smith", "create": True}).json()["matter"]
        assert first["case_id"] == "smith-v-jones"
        assert second["case_id"] == "smith-v-jones-2"
        assert client.get("/matter", params={"case_id": "smith-v-jones"}).json()["matter"]["plaintiff"] == "Ann Smith"
        # A matter saved without an ID is still its own matter, never "unassigned".
        untitled = client.post("/matter", json={"title": "Estate of Lee"}).json()["matter"]
        assert untitled["case_id"] == "estate-of-lee"
        # Editing keeps the ID and the fields that were not sent.
        edited = client.post("/matter", json={"case_id": "smith-v-jones", "defendant": "Bob Jones"}).json()["matter"]
        assert edited["case_id"] == "smith-v-jones" and edited["plaintiff"] == "Ann Smith" and edited["defendant"] == "Bob Jones"
    finally:
        app_module.STORE = previous


def test_dates_are_read_from_sentences_with_inferred_years_marked():
    events = dated_events(
        "Email from Bob Jones to Ann Smith, April 8, 2025: 'I paid April rent on April 3 by check.' "
        "The deposit cleared on 2025-04-09. Meeting at 10 a.m. on May 2 was cancelled."
    )
    assert [e["event_date"] for e in events] == ["2025-04-08", "2025-04-09", "2025-05-02"]
    assert events[0]["also_mentions"] == [{"event_date": "2025-04-03", "date_label": "Apr 3, 2025", "year_inferred": True}]
    assert events[2]["year_inferred"] is True
    assert dated_events("No dates here. Section 8.2 applies.") == []


def test_harbor_point_timeline_is_in_date_order_with_sources():
    store = WorkspaceStore(Path(tempfile.mkdtemp()))
    seed_harbor_point_demo(store)
    items = store.timeline(case_id=CASE_ID)
    dated = [item for item in items if item["dated"]]
    assert [item["event_date"] for item in dated] == sorted(item["event_date"] for item in dated)
    firsts = [(item["event_date"], item["title"]) for item in dated[:5]]
    assert firsts[0] == ("2026-01-02", "HP-001 Master Services Agreement")
    assert ("2026-02-01", "HP-006 Board Minutes Excerpt") in firsts
    assert ("2026-02-06", "HP-004 Courier Delivery Receipt") in firsts
    assert all(item["citation"] for item in items)
    assert not items[-1]["dated"]  # undated material is listed last, not dropped
