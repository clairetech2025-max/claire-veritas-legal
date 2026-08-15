#!/usr/bin/env python3
from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from web.services.workspace import WorkspaceStore


ROOT = Path(__file__).resolve().parent
CASE_ID = "harbor-point-commercial-dispute"


DEMO_MATTER = {
    "case_id": CASE_ID,
    "title": "Harbor Point Commercial Dispute",
    "court_profile_id": "federal_district_civil",
    "court_name": "United States District Court",
    "district": "Northern District",
    "jurisdiction": "Federal",
    "matter_type": "Federal District Civil",
    "practice_area": "Commercial Litigation",
    "plaintiff": "Harbor Point Holdings, LLC",
    "defendant": "North Coast Development Group, Inc.",
    "counsel": "Sample Demo Counsel",
    "billing_increment_minutes": 15,
    "billing_rate": 0.0,
    "confidentiality_level": "Sample Demo Matter",
    "notes": "Sample Demo Matter for product review. Fictional data only; no real client records.",
}


DEMO_EVIDENCE = [
    {
        "file_name": "HP-001 Master Services Agreement.txt",
        "source_type": "demo_exhibit",
        "text": (
            "Exhibit HP-001. Master Services Agreement dated January 2, 2026 between "
            "Harbor Point Holdings, LLC and North Coast Development Group, Inc. Section 8.2 "
            "requires written notice and a ten business day cure period before termination "
            "for missed milestone payments. The agreement lists Project Harbor as the "
            "covered commercial redevelopment project."
        ),
    },
    {
        "file_name": "HP-002 Notice of Default.txt",
        "source_type": "demo_exhibit",
        "text": (
            "Exhibit HP-002. Notice of Default dated February 3, 2026 states that North "
            "Coast failed to fund Draw Request 17 and gives ten business days to cure. "
            "The notice says Harbor Point will consider termination if payment is not "
            "received by February 17, 2026."
        ),
    },
    {
        "file_name": "HP-003 Termination Letter.txt",
        "source_type": "demo_exhibit",
        "text": (
            "Exhibit HP-003. Termination letter dated February 12, 2026 states that Harbor "
            "Point terminated the services agreement effective immediately because North "
            "Coast did not cure the funding default. The letter references the February 3 "
            "notice and attaches an exhibit index."
        ),
    },
    {
        "file_name": "HP-004 Courier Delivery Receipt.txt",
        "source_type": "demo_exhibit",
        "text": (
            "Exhibit HP-004. Courier delivery receipt shows the notice packet delivered to "
            "North Coast's registered office on February 6, 2026 at 10:14 a.m. The receipt "
            "is signed by J. Morales and lists the tracking number HPD-20488."
        ),
    },
    {
        "file_name": "HP-005 North Coast Cure Response.txt",
        "source_type": "demo_exhibit",
        "text": (
            "Exhibit HP-005. North Coast response dated February 14, 2026 disputes the "
            "termination and states the cure period could not have expired before February "
            "20, 2026 because notice was not received until February 6. North Coast also "
            "states the wire transfer was scheduled for February 18."
        ),
    },
    {
        "file_name": "HP-006 Board Minutes Excerpt.txt",
        "source_type": "demo_exhibit",
        "text": (
            "Exhibit HP-006. Harbor Point board minutes from February 1, 2026 authorize "
            "management to prepare a termination letter before the notice of default was "
            "sent. The minutes say the company had already decided to replace North Coast "
            "unless immediate payment was received."
        ),
    },
    {
        "file_name": "HP-007 Attorney Review Note.txt",
        "source_type": "demo_analysis_note",
        "text": (
            "Attorney-review note. Potential inconsistency: the termination letter was "
            "sent February 12, 2026, while the notice receipt and ten business day cure "
            "period suggest the cure deadline may not have expired. Source review should "
            "compare Exhibit HP-001 Section 8.2, Exhibit HP-002, Exhibit HP-003, "
            "Exhibit HP-004, and Exhibit HP-005."
        ),
    },
]

DEMO_DOCKET = """Case No. 3:26-cv-04118
Plaintiff: Harbor Point Holdings, LLC
Defendant: North Coast Development Group, Inc.
1 2026-03-01 Complaint for breach of commercial redevelopment agreement filed by Harbor Point Holdings, LLC.
2 2026-03-04 Civil cover sheet and summons issued.
3 2026-03-21 Notice of appearance filed for North Coast Development Group, Inc.
4 2026-04-08 Motion to dismiss filed by North Coast Development Group, Inc.
5 2026-04-22 Opposition to motion to dismiss filed by Harbor Point Holdings, LLC.
6 2026-05-03 Order setting initial case management conference.
"""


def seed_harbor_point_demo(store: WorkspaceStore) -> dict[str, Any]:
    matter = store.upsert_matter(DEMO_MATTER)
    total_chunks = 0
    imported = []
    for item in DEMO_EVIDENCE:
        result = store.ingest_text(
            item["text"],
            case_id=CASE_ID,
            case_title=matter["title"],
            source_type=item["source_type"],
            file_name=item["file_name"],
            mime_type="text/plain",
            metadata={"demo": True, "fictional": True, "sample_matter": "Harbor Point Commercial Dispute"},
        )
        total_chunks += int(result.get("chunks", 0))
        imported.extend(result.get("items", []))

    docket = store.import_docket_payload(
        DEMO_DOCKET,
        case_id=CASE_ID,
        court_name=DEMO_MATTER["court_name"],
        source_name="Harbor Point sample docket",
    )
    matter = store.upsert_matter(DEMO_MATTER)
    hits = store.search(
        "termination notice cure period expired delivery receipt February 2026",
        case_id=CASE_ID,
        top_k=8,
    )
    analysis = store.analyze_matter(
        query="termination notice cure period contradiction",
        case_id=CASE_ID,
        top_k=10,
    )
    trace_id = store.append_trace(
        {
            "timestamp": time.time(),
            "case_id": CASE_ID,
            "event_type": "demo_matter_loaded",
            "title": "Harbor Point Commercial Dispute loaded",
            "summary": "Loaded fictional sample matter with evidence, docket entries, chronology, contradictions, source citations, and attorney-review packet support.",
            "metadata": {
                "demo": True,
                "fictional": True,
                "chunks": total_chunks,
                "docket_entries": docket.get("recorded", 0),
                "top_hits": hits[:3],
                "anomalies": analysis.get("anomalies", []),
            },
        }
    )
    return {
        "ok": True,
        "case_id": CASE_ID,
        "matter": matter,
        "chunks": total_chunks,
        "evidence_items": len(imported),
        "docket_entries": docket.get("recorded", 0),
        "trace_id": trace_id,
        "bundle": store.matter_profile(CASE_ID),
        "search_preview": hits,
        "analysis": analysis,
    }


def main() -> int:
    store = WorkspaceStore(ROOT)
    result = seed_harbor_point_demo(store)
    print(f"Seeded Veritas Legal demo matter: {result['case_id']}")
    print(f"Chunks written: {result['chunks']}")
    print(f"Docket entries: {result['docket_entries']}")
    print(f"Trace ID: {result['trace_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
