from __future__ import annotations

import base64
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ENTRY_RE = re.compile(
    r"^\s*(?P<number>\d+)\s+(?P<date>\d{1,2}/\d{1,2}/\d{2,4})\s+(?P<title>.+?)(?:\s*\(.*)?$"
)
ISO_ENTRY_RE = re.compile(
    r"^\s*(?P<number>\d+)\s+(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<title>.+?)(?:\s*\(.*)?$"
)


def _parse_date(value: str) -> Optional[float]:
    value = (value or "").strip()
    if not value:
        return None
    formats = ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).timestamp()
        except Exception:
            continue
    return None


def _clean_summary(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def _event_type(title: str) -> str:
    lowered = (title or "").lower()
    probes = [
        ("complaint", ["complaint", "petition"]),
        ("answer", ["answer"]),
        ("motion", ["motion", "mtn"]),
        ("order", ["order", "judgment", "decree"]),
        ("hearing", ["hearing", "oral argument", "conference"]),
        ("brief", ["brief", "reply", "opposition", "memorandum"]),
        ("discovery", ["interrogatory", "production", "admission", "discovery"]),
        ("notice", ["notice"]),
        ("appearance", ["appearance", "substitution", "withdrawal"]),
    ]
    for label, words in probes:
        if any(word in lowered for word in words):
            return label
    return "docket_entry"


def _doc_citation(case_number: str, number: str) -> str:
    return f"[Dkt. {number}]" if number else f"[{case_number or 'docket'}]"


def parse_docket_text(text: str, *, case_id: Optional[str] = None, court_name: Optional[str] = None) -> Dict[str, Any]:
    lines = [line.rstrip() for line in (text or "").splitlines()]
    events: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    case_number = ""
    parties = {"plaintiff": "", "defendant": ""}

    def flush() -> None:
        nonlocal current
        if not current:
            return
        current["summary"] = _clean_summary(current.get("summary", ""))
        current["metadata"] = current.get("metadata", {})
        current["metadata"]["event_type"] = _event_type(current.get("title", ""))
        events.append(current)
        current = None

    for line in lines:
        raw = line.strip()
        if not raw:
            continue

        if not case_number:
            case_match = re.search(r"Case(?:\s+No\.?| Number)?\s*[:#]?\s*([A-Za-z0-9:\-._/]+)", raw, re.I)
            if case_match:
                case_number = case_match.group(1).strip()

        if not parties["plaintiff"]:
            p_match = re.search(r"Plaintiff(?:s)?\s*[:\-]\s*(.+)", raw, re.I)
            if p_match:
                parties["plaintiff"] = p_match.group(1).strip()
        if not parties["defendant"]:
            d_match = re.search(r"Defendant(?:s)?\s*[:\-]\s*(.+)", raw, re.I)
            if d_match:
                parties["defendant"] = d_match.group(1).strip()

        match = ENTRY_RE.match(raw) or ISO_ENTRY_RE.match(raw)
        if match:
            flush()
            number = match.group("number").strip()
            date = match.group("date").strip()
            title = match.group("title").strip()
            current = {
                "entry_number": number,
                "date": date,
                "timestamp": _parse_date(date),
                "title": title,
                "summary": title,
                "citation": _doc_citation(case_number, number),
                "source_type": "docket_entry",
                "source_name": "docket_text",
                "metadata": {"raw_line": raw, "court_name": court_name or "Federal Court"},
                "case_id": case_id or case_number or "unassigned",
            }
            continue

        if current:
            current["summary"] = f"{current.get('summary', '')} {raw}".strip()
            continue

        fallback_number = str(len(events) + 1)
        current = {
            "entry_number": fallback_number,
            "date": "",
            "timestamp": None,
            "title": raw,
            "summary": raw,
            "citation": _doc_citation(case_number, fallback_number),
            "source_type": "docket_entry",
            "source_name": "docket_text",
            "metadata": {"raw_line": raw, "court_name": court_name or "Federal Court"},
            "case_id": case_id or case_number or "unassigned",
        }

    flush()

    for event in events:
        if not event.get("timestamp"):
            event["timestamp"] = datetime.utcnow().timestamp()
        event.setdefault("metadata", {})
        event["metadata"].update(
            {
                "case_number": case_number,
                "court_name": court_name or "Federal Court",
                "plaintiff": parties["plaintiff"],
                "defendant": parties["defendant"],
            }
        )

    return {
        "case_id": case_id or case_number or "unassigned",
        "case_number": case_number,
        "court_name": court_name or "Federal Court",
        "parties": parties,
        "events": events,
        "source_type": "text",
        "summary": docket_summary(events),
    }


def parse_docket_json(payload: Any, *, case_id: Optional[str] = None, court_name: Optional[str] = None) -> Dict[str, Any]:
    if isinstance(payload, list):
        events = payload
        meta: Dict[str, Any] = {}
    elif isinstance(payload, dict):
        if "events" in payload and isinstance(payload.get("events"), list):
            events = payload["events"]
        elif "docket_entries" in payload and isinstance(payload.get("docket_entries"), list):
            events = payload["docket_entries"]
        elif "entries" in payload and isinstance(payload.get("entries"), list):
            events = payload["entries"]
        else:
            events = [payload]
        meta = dict(payload.get("case", {})) if isinstance(payload.get("case"), dict) else {}
        meta.update({k: v for k, v in payload.items() if k in {"case_id", "case_number", "court_name", "parties"}})
    else:
        events = []
        meta = {}

    normalized: List[Dict[str, Any]] = []
    for index, event in enumerate(events, start=1):
        if not isinstance(event, dict):
            normalized.append(
                {
                    "entry_number": str(index),
                    "title": str(event),
                    "summary": str(event),
                    "timestamp": datetime.utcnow().timestamp(),
                    "citation": _doc_citation(str(meta.get("case_number", "")), str(index)),
                    "source_type": "docket_entry",
                    "source_name": "docket_json",
                    "metadata": {"raw": event},
                }
            )
            continue
        raw_number = event.get("entry_number") or event.get("number") or event.get("docket_no") or index
        title = event.get("title") or event.get("description") or event.get("text") or event.get("summary") or ""
        date = str(event.get("date") or event.get("filed_at") or event.get("timestamp") or "")
        timestamp = event.get("timestamp")
        if isinstance(timestamp, str):
            try:
                timestamp = float(timestamp)
            except Exception:
                timestamp = None
        if not timestamp and date:
            timestamp = _parse_date(date)
        normalized.append(
            {
                "entry_number": str(raw_number),
                "date": date,
                "timestamp": timestamp or datetime.utcnow().timestamp(),
                "title": title,
                "summary": _clean_summary(event.get("summary") or title),
                "citation": event.get("citation") or _doc_citation(str(meta.get("case_number", "")), str(raw_number)),
                "source_type": "docket_entry",
                "source_name": "docket_json",
                "metadata": {k: v for k, v in event.items() if k not in {"title", "description", "text", "summary"}},
                "case_id": case_id or str(meta.get("case_id") or meta.get("case_number") or "unassigned"),
            }
        )

    return {
        "case_id": case_id or str(meta.get("case_id") or meta.get("case_number") or "unassigned"),
        "case_number": str(meta.get("case_number") or ""),
        "court_name": court_name or str(meta.get("court_name") or "Federal Court"),
        "parties": meta.get("parties") if isinstance(meta.get("parties"), dict) else {"plaintiff": "", "defendant": ""},
        "events": normalized,
        "source_type": "json",
        "summary": docket_summary(normalized),
    }


def parse_docket_payload(payload: Any, *, case_id: Optional[str] = None, court_name: Optional[str] = None) -> Dict[str, Any]:
    if isinstance(payload, str):
        stripped = payload.strip()
        if not stripped:
            return {
                "case_id": case_id or "unassigned",
                "case_number": "",
                "court_name": court_name or "Federal Court",
                "parties": {"plaintiff": "", "defendant": ""},
                "events": [],
                "source_type": "text",
                "summary": docket_summary([]),
            }
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                data = json.loads(stripped)
            except Exception:
                return parse_docket_text(payload, case_id=case_id, court_name=court_name)
            return parse_docket_json(data, case_id=case_id, court_name=court_name)
        return parse_docket_text(payload, case_id=case_id, court_name=court_name)
    return parse_docket_json(payload, case_id=case_id, court_name=court_name)


def docket_summary(events: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    timeline: List[str] = []
    total = 0
    for event in events:
        total += 1
        event_type = str(event.get("metadata", {}).get("event_type") or _event_type(str(event.get("title", ""))))
        counts[event_type] = counts.get(event_type, 0) + 1
        title = str(event.get("title", "")).strip()
        if title:
            timeline.append(title)
    return {
        "count": total,
        "event_types": counts,
        "keywords": timeline[:12],
    }
