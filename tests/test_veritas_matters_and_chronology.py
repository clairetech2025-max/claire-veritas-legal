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


def test_business_days_skip_weekends_and_flag_federal_holidays():
    from datetime import date
    from web.services.record_checks import add_days, federal_holidays

    assert federal_holidays(2026)[date(2026, 2, 16)] == "Presidents' Day"
    # Ten business days after Feb 3 and Feb 6, 2026, with and without Presidents' Day.
    assert add_days(date(2026, 2, 3), 10, business=True) == date(2026, 2, 17)
    assert add_days(date(2026, 2, 6), 10, business=True) == date(2026, 2, 20)
    assert add_days(date(2026, 2, 6), 10, business=True, skip_holidays=True) == date(2026, 2, 23)
    assert add_days(date(2025, 4, 1), 5, business=False) == date(2025, 4, 6)


def test_harbor_point_issues_come_from_the_record_with_sources():
    store = WorkspaceStore(Path(tempfile.mkdtemp()))
    seed_harbor_point_demo(store)
    from web.services.record_checks import find_issues

    issues = find_issues(store.list_evidence(case_id=CASE_ID), store.timeline(case_id=CASE_ID))
    kinds = [issue["kind"] for issue in issues]
    assert kinds.count("Deadline") == 1 and "Sequence" in kinds and "Contested" in kinds
    deadline = next(issue for issue in issues if issue["kind"] == "Deadline")
    assert "Feb 12, 2026" in deadline["summary"] and "Feb 17, 2026" in deadline["summary"] and "Feb 20, 2026" in deadline["summary"]
    assert "Presidents' Day" in deadline["summary"]
    assert all(issue["citations"] for issue in issues)
    # A contract clause about termination is not a termination step.
    assert not any("Master Services Agreement (Jan 2" in issue["summary"] for issue in issues if issue["kind"] == "Sequence")


def test_memo_has_no_invented_scores_or_placeholder_scaffolds():
    previous = app_module.STORE
    try:
        client = _client(Path(tempfile.mkdtemp()))
        client.post("/demo-matter")
        memo = client.post("/export_packet", json={"case_id": CASE_ID, "template_id": "case_theory_memo"}).json()
        text = memo.get("content") or memo.get("markdown")
        for bad in ("Confidence", "scaffold", "Unassigned", "CLAIRE // VERITAS", "[["):
            assert bad not in text, bad
        assert "## 3. Chronology" in text and "Jan 2, 2026:" in text
        assert "[To be stated by counsel.]" in text
        assert "Presidents' Day" in text
    finally:
        app_module.STORE = previous
