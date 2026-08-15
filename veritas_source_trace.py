from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from memory_io import append_jsonl


SOURCE_CLASSES = {
    "user_evidence": "User-provided evidence",
    "courtlistener_public_case_law": "CourtListener public case law",
    "courtlistener_public_docket_metadata": "CourtListener public docket metadata",
    "recap_docket_or_document_data": "RECAP docket/document data",
    "sec_edgar_public_filing": "SEC EDGAR public filing data",
    "generated_analysis": "Generated analysis",
}


def source_trace_path(root: Path) -> Path:
    return root / "memory" / "veritas_source_traces.jsonl"


def build_source_trace(
    *,
    source_class: str,
    action: str,
    query: str = "",
    source_url: str | None = None,
    source_ids: dict[str, Any] | None = None,
    warnings: list[dict[str, Any]] | None = None,
    case_id: str | None = None,
) -> dict[str, Any]:
    payload = {
        "trace_id": "vsrc_" + hashlib.sha256(f"{time.time_ns()}|{source_class}|{query}".encode()).hexdigest()[:16],
        "timestamp_ns": time.time_ns(),
        "case_id": case_id or "unassigned",
        "source_class": source_class,
        "source_label": SOURCE_CLASSES.get(source_class, source_class),
        "action": action,
        "query": query,
        "source_url": source_url,
        "source_ids": source_ids or {},
        "warnings": warnings or [],
    }
    return payload


def write_source_trace(root: Path, trace: dict[str, Any]) -> dict[str, Any]:
    append_jsonl(str(source_trace_path(root)), trace)
    return trace
