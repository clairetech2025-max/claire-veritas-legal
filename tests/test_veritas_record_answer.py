from web.services.record_answer import HEADER, build_record_answer
from web.services.record_checks import computed_date_facts


def _timeline_item(day, summary, title, citation):
    return {
        "dated": True,
        "event_date": day,
        "date_label": day,
        "summary": summary,
        "title": title,
        "citation": citation,
    }


RECORDS = [
    {"text": "Section 8.2 requires written notice and a ten business day cure period before termination.",
     "title": "HP-001 Agreement", "citation": "[HP-001 #1]", "source_name": "HP-001 Agreement.txt"},
]
TIMELINE = [
    _timeline_item("2026-02-03", "Notice of Default dated February 3, 2026 gives ten business days to cure.",
                   "HP-002 Notice of Default", "[HP-002 #1]"),
    _timeline_item("2026-02-03", "The letter references the February 3 notice.", "HP-003 Termination Letter", "[HP-003 #1]"),
    _timeline_item("2026-03-21", "Notice of appearance filed for North Coast.", "Dkt. 3", "[Dkt. 3]"),
]
HITS = [
    {"citation": "[HP-004 #1]", "text": "Exhibit HP-004. The receipt is signed by J. Morales and lists the tracking number."},
]


def test_cure_period_counts_each_start_date_once_and_ignores_court_filings():
    facts = computed_date_facts(RECORDS, TIMELINE)
    cure_lines = [line for line in facts.splitlines() if "cure period counted from" in line]
    assert len(cure_lines) == 1
    assert "Feb 3, 2026" in cure_lines[0] and "Feb 17, 2026" in cure_lines[0]
    assert "Mar 21" not in facts.split("Periods and deadlines")[1]


def test_record_answer_quotes_sources_and_skips_bare_labels():
    answer = build_record_answer("Who signed the receipt?", HITS, RECORDS, TIMELINE, "Harbor Point")
    assert answer.startswith(HEADER)
    assert "J. Morales" in answer and "[HP-004 #1]" in answer
    assert "“Exhibit HP-004.”" not in answer
    assert "Legal conclusions remain with counsel" in answer


def test_record_answer_includes_deadlines_for_date_questions():
    answer = build_record_answer("When did the cure period end?", HITS, RECORDS, TIMELINE)
    assert "Deadlines computed from the record" in answer
    assert "Feb 17, 2026" in answer


def test_record_answer_says_so_when_nothing_matches():
    answer = build_record_answer("zebra migration patterns", [], [], [])
    assert "No document in this matter addresses that question yet" in answer
