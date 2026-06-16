#!/usr/bin/env python3
from __future__ import annotations

import time
from pathlib import Path

from web.services.workspace import WorkspaceStore


ROOT = Path(__file__).resolve().parent
CASE_ID = "demo-access-v-city"


DEMO_MATTER = {
    "case_id": CASE_ID,
    "title": "Demo Matter: Access Coalition v. City Transit",
    "court_profile_id": "federal_district_civil",
    "court_name": "U.S. District Court",
    "district": "Northern District of California",
    "jurisdiction": "Federal",
    "matter_type": "civil",
    "practice_area": "Civil Rights / Accessibility",
    "plaintiff": "Access Coalition",
    "defendant": "City Transit Authority",
    "counsel": "Demo Counsel",
    "billing_increment_minutes": 15,
    "billing_rate": 0.0,
    "confidentiality_level": "Demo",
    "notes": "Synthetic demo matter. Not legal advice. No real client data.",
}


DEMO_EVIDENCE = [
    {
        "file_name": "exhibit-a-service-notice.txt",
        "source_type": "demo_exhibit",
        "text": (
            "Exhibit A. On March 2, 2026, City Transit posted a service notice stating "
            "that elevator outages affected the Central Station platform. The notice "
            "listed alternate routing but did not identify accessible shuttle coverage."
        ),
    },
    {
        "file_name": "exhibit-b-rider-complaint.txt",
        "source_type": "demo_exhibit",
        "text": (
            "Exhibit B. A rider complaint dated March 4, 2026 reports missed medical "
            "appointments after the Central Station elevator outage. The complaint "
            "references prior outage reports from February 2026."
        ),
    },
    {
        "file_name": "exhibit-c-maintenance-log.txt",
        "source_type": "demo_exhibit",
        "text": (
            "Exhibit C. Maintenance log summary states that the Central Station elevator "
            "had unresolved parts delays from February 18 through March 6, 2026. "
            "The log identifies daily inspections but no permanent repair during that window."
        ),
    },
    {
        "file_name": "exhibit-d-policy-excerpt.txt",
        "source_type": "demo_policy",
        "text": (
            "Exhibit D. Transit accessibility policy requires reasonable alternate access "
            "planning when elevator outages affect station entry or platform access. "
            "The policy requires documentation of notice, alternate routing, and service continuity."
        ),
    },
]


def main() -> int:
    store = WorkspaceStore(ROOT)
    matter = store.upsert_matter(DEMO_MATTER)
    total_chunks = 0
    for item in DEMO_EVIDENCE:
        result = store.ingest_text(
            item["text"],
            case_id=CASE_ID,
            case_title=matter["title"],
            source_type=item["source_type"],
            file_name=item["file_name"],
            mime_type="text/plain",
            metadata={"demo": True, "synthetic": True},
        )
        total_chunks += int(result.get("chunks", 0))

    hits = store.search("elevator outage accessible alternate routing", case_id=CASE_ID, top_k=5)
    trace_id = store.append_trace(
        {
            "timestamp": time.time(),
            "case_id": CASE_ID,
            "event_type": "demo_seed",
            "title": "Seeded synthetic Veritas Legal demo matter",
            "summary": "Created synthetic evidence, matter profile, searchable records, and a replayable trace.",
            "metadata": {
                "demo": True,
                "synthetic": True,
                "chunks": total_chunks,
                "top_hits": hits[:3],
            },
        }
    )
    print(f"Seeded Veritas Legal demo matter: {CASE_ID}")
    print(f"Chunks written: {total_chunks}")
    print(f"Trace ID: {trace_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
