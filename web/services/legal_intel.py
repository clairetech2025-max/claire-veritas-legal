from __future__ import annotations

import math
import json
import re
import time
import textwrap
from collections import Counter
from io import BytesIO
from typing import Any, Dict, List, Optional

from .record_checks import find_issues

try:
    import docx  # type: ignore
except Exception:  # pragma: no cover - optional export dependency
    docx = None

try:
    from fpdf import FPDF  # type: ignore
except Exception:  # pragma: no cover - optional export dependency
    FPDF = None


COURT_PROFILES: List[Dict[str, Any]] = [
    {
        "id": "federal_district_civil",
        "name": "Federal District Civil",
        "scope": "National baseline for federal civil litigation",
        "caption_notes": ["Use court caption and docket number", "Verify local rules before filing"],
        "motion_notes": ["Include proposed order where required", "Verify page limits and judge-specific rules"],
        "artifact_defaults": ["complaint", "summons", "civil cover sheet", "motion to compel", "motion to dismiss", "summary judgment", "declaration", "exhibit index"],
        "local_rules_source": "U.S. Courts national rules + local district rules",
        "template_priority": ["motion_to_compel", "motion_to_dismiss", "summary_judgment", "declaration", "exhibit_index"],
        "page_limit_hint": "Vary by court and judge; verify locally",
    },
    {
        "id": "federal_appellate",
        "name": "Federal Appellate",
        "scope": "Circuit appeal workflow",
        "caption_notes": ["Track circuit and case number carefully", "Use appendix and certificate of compliance workflows"],
        "motion_notes": ["Briefs, appendices, and motion practice follow FRAP and circuit rules"],
        "artifact_defaults": ["notice of appeal", "appellant brief", "appellee brief", "reply brief", "appendix", "certificate of compliance"],
        "local_rules_source": "FRAP + circuit local rules",
        "template_priority": ["appendix", "brief", "certificate_of_compliance", "timeline_summary"],
        "page_limit_hint": "Circuit-specific; verify before export",
    },
    {
        "id": "federal_bankruptcy",
        "name": "Federal Bankruptcy",
        "scope": "Bankruptcy case and adversary workflow",
        "caption_notes": ["Use official forms without alteration where required"],
        "motion_notes": ["Bankruptcy form fidelity is strict; verify chapter-specific rules"],
        "artifact_defaults": ["petition", "schedules", "statement of financial affairs", "proof of claim", "motion", "order"],
        "local_rules_source": "FRBP + official bankruptcy forms + local bankruptcy rules",
        "template_priority": ["motion_to_compel", "motion", "declaration", "exhibit_index"],
        "page_limit_hint": "Form-driven; local rules still matter",
    },
    {
        "id": "nd_california",
        "name": "Northern District of California",
        "scope": "Example district profile with explicit motion workflow",
        "caption_notes": ["Use court caption and filing number", "Verify judge-specific instructions"],
        "motion_notes": ["Motion / opposition / reply page limits are court- and judge-driven", "Proposed order often required", "Courtesy copies generally not submitted unless required"],
        "artifact_defaults": ["motion", "opposition", "reply", "proposed order", "exhibit index"],
        "local_rules_source": "N.D. Cal. local rules and judge procedures",
        "template_priority": ["motion_to_compel", "motion_to_dismiss", "summary_judgment", "proposed_order"],
        "page_limit_hint": "Verify local rule and judge standing order",
    },
    {
        "id": "cd_california",
        "name": "Central District of California",
        "scope": "Example district profile with chambers-copy workflow",
        "caption_notes": ["Check e-filing and chambers-copy requirements"],
        "motion_notes": ["Proposed documents may need separate lodging and chambers delivery", "Judge-specific procedures govern final packaging"],
        "artifact_defaults": ["motion", "proposed order", "lodged copy", "exhibit index"],
        "local_rules_source": "C.D. Cal. local rules and procedures",
        "template_priority": ["motion_to_compel", "motion_to_dismiss", "summary_judgment", "declaration"],
        "page_limit_hint": "Verify local rule and judge-specific instructions",
    },
]


FILING_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "motion_to_compel",
        "title": "Motion to Compel + MPA",
        "category": "motion",
        "purpose": "Compel deficient discovery responses or production.",
        "sections": ["caption", "notice", "motion", "memorandum of points and authorities", "statement of facts", "argument", "request for relief", "declaration", "exhibit index", "proposed order", "proof of service"],
        "required_inputs": ["discovery requests", "responses or non-responses", "deadlines", "case posture"],
    },
    {
        "id": "motion_to_dismiss",
        "title": "Motion to Dismiss",
        "category": "motion",
        "purpose": "Challenge pleading sufficiency or jurisdictional defects.",
        "sections": ["caption", "notice", "motion", "memorandum of points and authorities", "grounds", "argument", "request for relief", "proposed order", "proof of service"],
        "required_inputs": ["complaint", "causes of action", "jurisdiction facts", "defense theory"],
    },
    {
        "id": "summary_judgment",
        "title": "Motion for Summary Judgment",
        "category": "motion",
        "purpose": "Seek judgment based on undisputed facts and governing law.",
        "sections": ["caption", "notice", "motion", "memorandum of points and authorities", "statement of undisputed facts", "argument", "declaration", "exhibit index", "proposed order", "proof of service"],
        "required_inputs": ["material facts", "depositions", "declarations", "key exhibits"],
    },
    {
        "id": "request_for_admissions",
        "title": "Requests for Admissions",
        "category": "discovery",
        "purpose": "Pin down factual admissions and narrow disputes.",
        "sections": ["caption", "requests", "definitions", "instructions", "service"],
        "required_inputs": ["target facts", "identity of responding party", "discovery deadline"],
    },
    {
        "id": "interrogatories",
        "title": "Interrogatories",
        "category": "discovery",
        "purpose": "Force narrative answers and preserve impeachment material.",
        "sections": ["caption", "interrogatories", "definitions", "instructions", "service"],
        "required_inputs": ["issue list", "custodians", "timeline gaps"],
    },
    {
        "id": "requests_for_production",
        "title": "Requests for Production",
        "category": "discovery",
        "purpose": "Obtain documents, ESI, and metadata.",
        "sections": ["caption", "requests", "definitions", "instructions", "service"],
        "required_inputs": ["document categories", "custodians", "time frame"],
    },
    {
        "id": "declaration",
        "title": "Declaration",
        "category": "supporting",
        "purpose": "Authenticate exhibits and lay factual foundation.",
        "sections": ["caption", "declaration", "numbered paragraphs", "exhibit references", "signature", "proof of service"],
        "required_inputs": ["declarant identity", "facts to support", "exhibits"],
    },
    {
        "id": "proposed_order",
        "title": "Proposed Order",
        "category": "supporting",
        "purpose": "Provide judge-ready order language for motion disposition.",
        "sections": ["caption", "order title", "relief granted", "signature block"],
        "required_inputs": ["motion relief requested", "party names"],
    },
    {
        "id": "exhibit_index",
        "title": "Exhibit Index",
        "category": "supporting",
        "purpose": "Catalog exhibits, sources, and citations for filing or appendix use.",
        "sections": ["caption", "table of exhibits", "source citations", "authentication notes"],
        "required_inputs": ["exhibit list", "source citations", "page spans"],
    },
    {
        "id": "appendix",
        "title": "Appendix",
        "category": "appellate",
        "purpose": "Assemble record excerpts and documents for appellate filing.",
        "sections": ["caption", "appendix index", "record excerpts", "certificate of service"],
        "required_inputs": ["record items", "brief cites", "page limits"],
    },
    {
        "id": "timeline_summary",
        "title": "Timeline Summary",
        "category": "analysis",
        "purpose": "Compress record chronology into a filing-ready timeline.",
        "sections": ["caption", "timeline", "key events", "anomalies", "source anchors"],
        "required_inputs": ["event list", "dates", "source citations"],
    },
    {
        "id": "case_theory_memo",
        "title": "Case Theory Memo",
        "category": "analysis",
        "purpose": "State the strongest supported theory, alternatives, and pressure points.",
        "sections": ["caption", "question presented", "chronology", "most supported theory", "alternate theories", "evidence supporting each", "risk notes"],
        "required_inputs": ["key facts", "top documents", "opposing facts"],
    },
    {
        "id": "filing_checklist",
        "title": "Filing Checklist",
        "category": "operations",
        "purpose": "Track rule, form, signature, service, and exhibit readiness.",
        "sections": ["caption", "checklist items", "court rule notes", "service", "final review"],
        "required_inputs": ["court profile", "filing type", "required attachments"],
    },
]


PII_PATTERNS: List[Dict[str, Any]] = [
    {"label": "email", "pattern": re.compile(r"(?i)\b[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}\b")},
    {"label": "ssn", "pattern": re.compile(r"\b\d{3}-\d{2}-\d{4}\b")},
    {"label": "phone", "pattern": re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}(?!\d)")},
    {"label": "credit_card", "pattern": re.compile(r"\b(?:\d[ -]*?){13,16}\b")},
    {"label": "dob", "pattern": re.compile(r"(?i)\b(?:dob|date of birth)\s*[:\-]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")},
]


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _top_terms(records: List[Dict[str, Any]], limit: int = 6) -> List[str]:
    counter: Counter[str] = Counter()
    for record in records:
        text = " ".join(
            [
                str(record.get("title", "")),
                str(record.get("text", "")),
                " ".join(record.get("tags", []) or []),
                json.dumps(record.get("metadata", {}), ensure_ascii=False),
            ]
        )
        counter.update(term for term in _tokenize(text) if len(term) > 3)
    return [term for term, _ in counter.most_common(limit)]


def list_court_profiles() -> List[Dict[str, Any]]:
    return COURT_PROFILES


def get_court_profile(profile_id: Optional[str]) -> Dict[str, Any]:
    profile_id = (profile_id or "federal_district_civil").strip()
    for profile in COURT_PROFILES:
        if profile["id"] == profile_id:
            return profile
    return COURT_PROFILES[0]


def list_filing_templates() -> List[Dict[str, Any]]:
    return FILING_TEMPLATES


def get_template(template_id: Optional[str]) -> Dict[str, Any]:
    template_id = (template_id or "case_theory_memo").strip()
    for template in FILING_TEMPLATES:
        if template["id"] == template_id:
            return template
    return FILING_TEMPLATES[0]


def court_profile_report(profile: Dict[str, Any]) -> Dict[str, Any]:
    required_keys = [
        "id",
        "name",
        "scope",
        "caption_notes",
        "motion_notes",
        "artifact_defaults",
        "local_rules_source",
        "template_priority",
        "page_limit_hint",
    ]
    missing = [key for key in required_keys if key not in profile or profile.get(key) in (None, "", [], {})]
    local_notes = profile.get("local_rules_notes") or []
    source_files = profile.get("source_files") or []
    if isinstance(local_notes, str):
        local_notes = [local_notes]
    if isinstance(source_files, str):
        source_files = [source_files]
    return {
        "profile": profile,
        "missing_fields": missing,
        "local_rules_notes": local_notes,
        "source_files": source_files,
        "notes": [
            "Treat this profile as a local drafting preset, not an authoritative substitute for current court rules.",
            "Verify page limits, judge-specific procedures, and filing format before export.",
            "Update this profile with court-specific observations as you validate matters.",
        ],
        "ready": not bool(missing),
    }


def scan_sensitive_text(text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    sample = text or ""
    for item in PII_PATTERNS:
        matches = item["pattern"].finditer(sample)
        for match in matches:
            findings.append(
                {
                    "label": item["label"],
                    "value": match.group(0),
                    "start": match.start(),
                    "end": match.end(),
                }
            )
            if len(findings) >= 40:
                return findings
    return findings


def redact_sensitive_text(text: str) -> str:
    redacted = text or ""
    replacements = {
        "email": "[REDACTED EMAIL]",
        "ssn": "[REDACTED SSN]",
        "phone": "[REDACTED PHONE]",
        "credit_card": "[REDACTED CARD]",
        "dob": "[REDACTED DOB]",
    }
    for item in PII_PATTERNS:
        redacted = item["pattern"].sub(replacements[item["label"]], redacted)
    return redacted


def scan_packet(packet: Dict[str, Any]) -> Dict[str, Any]:
    sections = packet.get("sections", []) or []
    source_text = "\n\n".join(str(section) for section in sections)
    findings = scan_sensitive_text(source_text)
    return {
        "findings": findings,
        "count": len(findings),
        "labels": sorted({item["label"] for item in findings}),
        "has_sensitive_data": bool(findings),
    }


def default_matter(case_id: Optional[str], title: Optional[str] = None) -> Dict[str, Any]:
    matter_id = (case_id or "unassigned").strip() or "unassigned"
    matter_title = (title or matter_id.replace("-", " ").title()).strip()
    return {
        "case_id": matter_id,
        "case_number": "",
        "title": matter_title,
        "court_profile_id": "federal_district_civil",
        "court_name": "Federal District Court",
        "district": "",
        "jurisdiction": "Federal",
        "matter_type": "civil",
        "practice_area": "Litigation",
        "plaintiff": "",
        "defendant": "",
        "current_status": "Active",
        "counsel": "",
        "billing_increment_minutes": 15,
        "billing_rate": 0.0,
        "confidentiality_level": "Privileged",
        "notes": "",
        "updated_at": time.time(),
    }


def _dedupe_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    result: List[Dict[str, Any]] = []
    for record in records:
        key = str(record.get("id") or record.get("citation") or record.get("text") or "")[:240]
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result


def rank_scenarios(records: List[Dict[str, Any]], query: str = "") -> List[Dict[str, Any]]:
    terms = _top_terms(records, limit=8)
    query_tokens = set(_tokenize(query))
    issue_map = {
        "discovery": "Discovery pressure points and missing responses are visible in the record.",
        "motion": "Motion posture looks likely based on the strongest evidence cluster.",
        "timeline": "The timeline is the main organizing axis and likely to drive the theory.",
        "contradiction": "The record contains conflicts that should be elevated as contradictions.",
        "billing": "Billing and staffing workflow appears to be relevant to operational follow-through.",
    }
    best_label = "record-backed theory"
    if {"compel", "discovery", "rfa", "rog", "rpd"} & query_tokens or "discovery" in terms:
        best_label = "discovery-pressure theory"
    elif {"dismiss", "jurisdiction", "standing"} & query_tokens:
        best_label = "threshold-defense theory"
    elif {"summary", "judgment", "undisputed"} & query_tokens:
        best_label = "record-cleanup / summary-judgment theory"
    elif {"appeal", "brief", "appendix"} & query_tokens:
        best_label = "appellate-record theory"
    # VERITAS does not choose or score a theory of the case; that is counsel's call.
    # It reports what the record contains and points to the issues list.
    sources = {str(item.get("source_name") or item.get("title") or "") for item in records}
    sources.discard("")
    summary = (
        "No theory has been selected; that is for counsel. "
        "The issues list shows the points the record raises, each with its sources."
        if records else "No evidence is loaded for this matter yet."
    )
    focus = best_label if query_tokens and best_label != "record-backed theory" else ""
    return [{"label": "Record overview", "summary": summary + (f" The request suggests a {focus} focus." if focus else "")}]


def detect_anomalies(records: List[Dict[str, Any]], timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Issues found by the record checks (deadlines, sequence, contested facts)."""
    return find_issues(records, timeline)


def build_exhibit_index(records: List[Dict[str, Any]], limit: int = 12) -> List[Dict[str, Any]]:
    index: List[Dict[str, Any]] = []
    evidence = [
        record for record in _dedupe_records(records)
        if record.get("source_type") not in {"docket_entry", "docket", "draft", "chat", "observation", "analysis"}
        and record.get("source_name") not in {"docket_text", None, ""}
        and str(record.get("text", "")).strip()
    ]
    for i, record in enumerate(evidence[:limit], start=1):
        name = str(record.get("source_name") or "")
        index.append(
            {
                "label": f"Exhibit {chr(64 + ((i - 1) % 26) + 1)}",
                "title": re.sub(r"\.(txt|md|pdf|docx?|jsonl?|csv)$", "", name, flags=re.IGNORECASE) or record.get("title") or record.get("id") or "Exhibit",
                "citation": record.get("citation") or record.get("source_name") or "",
                "page": record.get("metadata", {}).get("page") if isinstance(record.get("metadata", {}), dict) else None,
                "source_type": record.get("source_type") or "record",
                "summary": _clip(record.get("text", ""), 200),
            }
        )
    return index


def estimate_billing(records: List[Dict[str, Any]], increment_minutes: int = 15, hourly_rate: float = 0.0) -> Dict[str, Any]:
    increment_minutes = max(1, int(increment_minutes or 15))
    base_minutes = 30 + (len(records) * 2)
    rounded_minutes = int(math.ceil(base_minutes / increment_minutes) * increment_minutes)
    hours = round(rounded_minutes / 60.0, 2)
    value = round(hours * float(hourly_rate or 0.0), 2)
    return {
        "increment_minutes": increment_minutes,
        "base_minutes": base_minutes,
        "rounded_minutes": rounded_minutes,
        "estimated_hours": hours,
        "estimated_value": value,
        "note": "Estimate is heuristic and should be edited by the lawyer or billing coordinator.",
    }


_FACT_SECTIONS = {"chronology", "statement of facts", "statement of undisputed facts", "timeline", "key events", "numbered paragraphs"}
_ISSUE_SECTIONS = {"anomalies", "risk notes"}
_SOURCE_SECTIONS = {"evidence supporting each", "source anchors", "source citations", "record excerpts", "exhibit references", "memorandum of points and authorities"}
_EXHIBIT_SECTIONS = {"exhibit index", "table of exhibits", "appendix index"}


def chronology_lines(timeline: List[Dict[str, Any]]) -> List[str]:
    lines = []
    for item in timeline:
        if not item.get("dated"):
            continue
        when = item.get("date_label", "")
        if item.get("year_inferred"):
            when += " (year inferred)"
        lines.append(f"{when}: {item.get('summary', '')} {item.get('citation', '')}".strip())
    return lines


def issue_lines(issues: List[Dict[str, Any]]) -> List[str]:
    return [
        f"{item.get('kind') or item.get('label', 'Issue').title()}: {item.get('summary', '')} {' '.join(item.get('citations') or [])}".strip()
        for item in issues
    ]


def _grounded_sections(
    template: Dict[str, Any],
    matter: Dict[str, Any],
    profile: Dict[str, Any],
    timeline: List[Dict[str, Any]],
    issues: List[Dict[str, Any]],
    source_notes: List[str],
    exhibit_index: List[Dict[str, Any]],
    query: str,
) -> List[str]:
    """One text block per template section, headed by the section name.

    Sections the record can fill (facts, chronology, issues, sources, exhibits)
    are filled from it with citations. Sections that need an attorney's
    judgment or knowledge say so in brackets instead of pretending.
    """
    facts = chronology_lines(timeline)
    issue_text = issue_lines(issues)
    no_issues = "No issues were found by the automated record checks. That is not a finding that none exist."
    blocks = []
    for name in template["sections"]:
        title = name[:1].upper() + name[1:]
        if name == "caption":
            parties = " v. ".join(bit for bit in [matter.get("plaintiff"), matter.get("defendant")] if bit)
            body = [matter.get("title", "Matter")]
            if parties and parties not in body[0]:
                body.append(parties)
            body.append(f"{matter.get('court_name') or 'Court not set'} ({profile['name']})")
            if matter.get("case_number"):
                body.append(f"Case No. {matter['case_number']}")
        elif name in _FACT_SECTIONS:
            body = [f"- {line}" for line in facts] or ["- No dated facts found in the record yet."]
            if name == "statement of undisputed facts":
                body.insert(0, "Dated statements from the record. Counsel must confirm which are undisputed; see the issues list for contested points.")
        elif name in _ISSUE_SECTIONS:
            body = [f"- {line}" for line in issue_text] or [no_issues]
        elif name in _SOURCE_SECTIONS:
            body = [f"- {note}" for note in source_notes] or ["- No source material loaded."]
            if name == "memorandum of points and authorities":
                body.insert(0, "[To be drafted by counsel. Record material available for the memorandum:]")
        elif name in _EXHIBIT_SECTIONS:
            body = [f"- {item['label']}: {item['title']} {item['citation'] or ''}".rstrip() for item in exhibit_index] or ["- No exhibits loaded."]
        elif name == "question presented":
            body = [f"As framed for this packet: {query.strip()}" if query.strip() else "[To be stated by counsel.]"]
        elif name in {"most supported theory", "alternate theories", "argument", "grounds"}:
            body = ["[To be drafted by counsel. The points the record raises are listed under "
                    + ("Risk notes." if "risk notes" in template["sections"] else "Issues for Attorney Review.") + "]"]
        else:
            body = [f"[To be drafted by counsel: {name}.]"]
        blocks.append("\n".join([title] + body))
    return blocks


def build_filing_packet(
    *,
    template_id: str,
    matter: Dict[str, Any],
    records: List[Dict[str, Any]],
    timeline: List[Dict[str, Any]],
    query: str = "",
    firm_profile: Optional[Dict[str, Any]] = None,
    authority: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    template = get_template(template_id)
    profile = get_court_profile(matter.get("court_profile_id"))
    scenarios = rank_scenarios(records, query=query)
    anomalies = detect_anomalies(records, timeline)
    exhibit_index = build_exhibit_index(records, limit=12)
    top_records = _dedupe_records(records)[:6]
    source_notes = [
        f"{_bracketed(item.get('citation') or item.get('source_name') or 'source')} {_clip(item.get('text', ''), 240)}"
        for item in top_records
        if str(item.get("text", "")).strip()
    ]
    brand = dict(firm_profile or {})
    authority_stamp = dict(authority or {})
    stamp_lines = list(authority_stamp.get("stamp_lines") or [])
    if not stamp_lines:
        stamp_lines = responsibility_lines(authority_stamp)
    sections = _grounded_sections(template, matter, profile, timeline, anomalies, source_notes, exhibit_index, query)
    return {
        "template": template,
        "court_profile": profile,
        "firm_profile": brand,
        "authority": authority_stamp,
        "responsibility_stamp": "\n".join(stamp_lines),
        "responsibility_lines": stamp_lines,
        "court_profile_report": court_profile_report(profile),
        "matter": matter,
        "records": records,
        "timeline": timeline,
        "scenarios": scenarios,
        "anomalies": anomalies,
        "exhibit_index": exhibit_index,
        "sections": sections,
        "sensitivity": scan_packet({"sections": sections}),
        "checklist": [
            "Confirm caption, docket, and parties",
            "Verify court and judge formatting rules",
            "Verify firm profile, staff roles, and responsibility stamps",
            "Verify signatures and service requirements",
            "Cross-check citations against the loaded record",
            "Review for privilege, sealing, and redaction issues",
            "Have attorney review before filing",
        ],
    }


NO_ISSUES_TEXT = "No issues were found by the automated record checks. That is not a finding that none exist."


def responsibility_lines(authority: Dict[str, Any]) -> List[str]:
    assignments = (authority or {}).get("assignments", {}) or {}
    return [
        f"{role}: {(assignments.get(key) or {}).get('full_name') or 'Not yet assigned'}"
        for role, key in (
            ("Prepared by", "prepared_by"), ("Reviewed by", "reviewed_by"), ("Approved by", "approved_by"),
            ("Signed by", "signed_by"), ("Filed by", "filed_by"),
        )
    ]


_PRODUCT_DEFAULTS = {"CLAIRE // VERITAS LEGAL", "Legal Intelligence Office"}


def _firm_value(firm: Dict[str, Any], key: str) -> str:
    """A firm profile value, blank while it is still the product's placeholder."""
    value = str((firm or {}).get(key) or "").strip()
    return "" if value in _PRODUCT_DEFAULTS else value


def _has_issue_section(template: Dict[str, Any]) -> bool:
    return any(name in _ISSUE_SECTIONS for name in template.get("sections", []))


def _clip(text: str, limit: int) -> str:
    """Shorten at a word boundary and mark the cut, so excerpts never end mid-word."""
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + " …"


def _bracketed(citation: str) -> str:
    citation = str(citation).strip()
    return citation if citation.startswith("[") else f"[{citation}]"


def _document_brand_lines(packet: Dict[str, Any]) -> List[str]:
    firm = packet.get("firm_profile", {}) or {}
    lines = []
    if _firm_value(firm, "name"):
        lines.append(_firm_value(firm, "name"))
    office_bits = [_firm_value(firm, "office_name"), str(firm.get("office_address") or "").strip()]
    office_bits = [bit for bit in office_bits if bit]
    if office_bits:
        lines.append(" • ".join(office_bits))
    if firm.get("phone") or firm.get("email") or firm.get("website"):
        contact_bits = [bit for bit in [firm.get("phone"), firm.get("email"), firm.get("website")] if bit]
        lines.append(" | ".join(str(bit) for bit in contact_bits))
    notice = firm.get("confidentiality_notice") or "CONFIDENTIAL AND ATTORNEY WORK PRODUCT."
    lines.append(str(notice))
    return lines


def packet_to_markdown(packet: Dict[str, Any], *, redact: bool = False) -> str:
    template = packet.get("template", {})
    matter = packet.get("matter", {})
    court_profile = packet.get("court_profile", {})
    firm_profile = packet.get("firm_profile", {})
    authority = packet.get("authority", {})
    court_profile_report_data = packet.get("court_profile_report", {})
    sensitivity = packet.get("sensitivity", {})
    scenarios = packet.get("scenarios", [])
    anomalies = packet.get("anomalies", [])
    exhibit_index = packet.get("exhibit_index", [])
    checklist = packet.get("checklist", [])
    sections = packet.get("sections", [])
    brand_lines = _document_brand_lines(packet)

    lines = [f"# {template.get('title', 'Filing Packet')}", ""]
    lines.extend(brand_lines)
    lines.extend(
        [
            "",
            "## Responsibility Stamp",
        ]
    )
    lines.extend(f"- {line}" for line in responsibility_lines(authority))
    lines.extend([
        "",
        "## Matter",
        f"- Case: {matter.get('title', 'Unassigned')}",
        f"- Case ID: {matter.get('case_id', 'unassigned')}",
        f"- Court: {matter.get('court_name', 'Federal Court')}",
        f"- Profile: {court_profile.get('name', 'Federal District Civil')}",
        f"- Practice Area: {matter.get('practice_area', 'Litigation')}",
        "",
    ])
    if not _has_issue_section(template):
        lines.append("## Issues for Attorney Review")
        lines.extend(f"- {line}" for line in issue_lines(anomalies) or [NO_ISSUES_TEXT])
        lines.append("")
    for idx, section in enumerate(sections, start=1):
        heading, _, body = section.partition("\n")
        lines.extend([f"## {idx}. {heading[:120]}", body, ""])

    lines.extend(["## Exhibit Index"])
    if exhibit_index:
        for item in exhibit_index:
            lines.append(
                f"- {item.get('label', 'Exhibit')}: {item.get('title', 'Untitled')} | {item.get('citation', '')} | {item.get('summary', '')}"
            )
    else:
        lines.append("- No exhibits loaded.")

    lines.extend(["", "## Filing Checklist"])
    for item in checklist:
        lines.append(f"- {item}")

    markdown = "\n".join(lines).strip() + "\n"
    return redact_sensitive_text(markdown) if redact else markdown


def packet_to_docx_bytes(packet: Dict[str, Any], *, redact: bool = False) -> bytes:
    if docx is None:
        raise RuntimeError("python-docx is not available")

    template = packet.get("template", {})
    matter = packet.get("matter", {})
    court_profile = packet.get("court_profile", {})
    firm_profile = packet.get("firm_profile", {})
    authority = packet.get("authority", {})
    court_profile_report_data = packet.get("court_profile_report", {})
    sensitivity = packet.get("sensitivity", {})
    scenarios = packet.get("scenarios", [])
    anomalies = packet.get("anomalies", [])
    exhibit_index = packet.get("exhibit_index", [])
    checklist = packet.get("checklist", [])
    sections = packet.get("sections", [])
    brand_lines = _document_brand_lines(packet)

    document = docx.Document()
    try:
        document.styles["Normal"].font.name = "Aptos"
    except Exception:
        pass
    try:
        section = document.sections[0]
        header = section.header.paragraphs[0]
        header.text = _firm_value(firm_profile, "name")
        footer = section.footer.paragraphs[0]
        footer.text = str(firm_profile.get("confidentiality_notice") or "CONFIDENTIAL AND ATTORNEY WORK PRODUCT.")
    except Exception:
        pass

    def add_bullets(lines: List[str]) -> None:
        for line in lines:
            document.add_paragraph(line, style="List Bullet")

    document.add_heading(template.get("title", "Filing Packet"), level=0)
    for line in brand_lines:
        document.add_paragraph(line)

    document.add_heading("Responsibility Stamp", level=1)
    add_bullets(
        [
            *responsibility_lines(authority),
        ]
    )

    document.add_heading("Matter", level=1)
    add_bullets(
        [
            f"Case: {matter.get('title', 'Unassigned')}",
            f"Case ID: {matter.get('case_id', 'unassigned')}",
            f"Court: {matter.get('court_name', 'Federal Court')}",
            f"Profile: {court_profile.get('name', 'Federal District Civil')}",
            f"Practice Area: {matter.get('practice_area', 'Litigation')}",
        ]
    )

    if not _has_issue_section(template):
        document.add_heading("Issues for Attorney Review", level=1)
        if anomalies:
            add_bullets(issue_lines(anomalies))
        else:
            document.add_paragraph(NO_ISSUES_TEXT)

    for idx, section in enumerate(sections, start=1):
        heading, _, body = section.partition("\n")
        document.add_heading(f"{idx}. {heading[:120] or 'Section'}", level=1)
        for paragraph in body.split("\n"):
            text = paragraph.strip()
            if text.startswith("- "):
                document.add_paragraph(text[2:], style="List Bullet")
            elif text:
                document.add_paragraph(text)

    document.add_heading("Exhibit Index", level=1)
    if exhibit_index:
        table = document.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        header = table.rows[0].cells
        header[0].text = "Label"
        header[1].text = "Title"
        header[2].text = "Citation"
        header[3].text = "Summary"
        for item in exhibit_index:
            row = table.add_row().cells
            row[0].text = str(item.get("label", "Exhibit"))
            row[1].text = str(item.get("title", "Untitled"))
            row[2].text = str(item.get("citation", ""))
            row[3].text = str(item.get("summary", ""))
    else:
        document.add_paragraph("No exhibits loaded.")

    document.add_heading("Filing Checklist", level=1)
    add_bullets([str(item) for item in checklist])

    if redact:
        for paragraph in document.paragraphs:
            paragraph.text = redact_sensitive_text(paragraph.text)
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    cell.text = redact_sensitive_text(cell.text)

    buffer = BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def packet_to_pdf_bytes(packet: Dict[str, Any], *, redact: bool = False) -> bytes:
    if FPDF is None:
        raise RuntimeError("fpdf is not available")

    markdown = packet_to_markdown(packet, redact=redact)
    firm_profile = packet.get("firm_profile", {}) or {}
    authority = packet.get("authority", {}) or {}

    class BrandPDF(FPDF):
        def header(self_nonlocal):
            self_nonlocal.set_font("Helvetica", "B", 11)
            self_nonlocal.cell(0, 6, txt=_firm_value(firm_profile, "name"), ln=1)
            self_nonlocal.set_font("Helvetica", size=9)
            office = " | ".join(
                [_firm_value(firm_profile, "office_name"), str(firm_profile.get("office_address") or "").strip()]
            ).strip(" |")
            if office:
                self_nonlocal.cell(0, 5, txt=office, ln=1)
            self_nonlocal.ln(1)

        def footer(self_nonlocal):
            self_nonlocal.set_y(-18)
            self_nonlocal.set_font("Helvetica", size=8)
            self_nonlocal.cell(0, 5, txt=str(firm_profile.get("confidentiality_notice") or "CONFIDENTIAL AND ATTORNEY WORK PRODUCT."), ln=1, align="C")
            self_nonlocal.cell(0, 5, txt=f"Page {self_nonlocal.page_no()}/{{nb}}", align="C")

    pdf = BrandPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)

    def write_wrapped_line(line: str, *, font_style: str = "", font_size: int = 11) -> None:
        pdf.set_font("Helvetica", font_style, font_size)
        safe_line = str(line or "").replace("•", " | ").replace("—", "-").replace("–", "-").replace("…", "...")
        safe_line = safe_line.encode("latin-1", "replace").decode("latin-1")
        wrapped = textwrap.wrap(
            safe_line,
            width=95,
            break_long_words=True,
            break_on_hyphens=False,
        ) or [""]
        for chunk in wrapped:
            pdf.set_x(pdf.l_margin)
            pdf.multi_cell(0, 6, txt=chunk)

    for line in markdown.splitlines():
        safe = line.encode("latin-1", "replace").decode("latin-1")
        if not safe.strip():
            pdf.ln(4)
            continue
        if safe.startswith("#"):
            level = len(safe) - len(safe.lstrip("#"))
            write_wrapped_line(safe.lstrip("#").strip(), font_style="B", font_size=15 if level == 1 else 12)
            continue
        write_wrapped_line(safe)
    output = pdf.output(dest="S")
    if isinstance(output, bytearray):
        return bytes(output)
    if isinstance(output, bytes):
        return output
    return str(output).encode("latin-1")
