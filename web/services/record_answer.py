"""Answers assembled directly from the matter record, for when no AI model is connected.

Nothing here is generated: every line is either a quoted sentence from a cited
record or a date/issue computed by the record checks. Conclusions stay with counsel.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .chronology import _sentences
from .record_checks import computed_date_facts

HEADER = "[record answer]"

_STOP = {
    "the", "and", "for", "was", "were", "what", "when", "where", "which", "who", "whom", "does", "did", "that",
    "this", "with", "from", "have", "has", "had", "about", "into", "there", "their", "they", "them", "then",
    "than", "will", "would", "could", "should", "can", "say", "says", "said", "record", "matter", "case", "tell",
    "show", "give", "please", "any", "all", "are", "our", "your", "you", "how", "why", "its", "it's", "is", "of",
}
_DATE_WORDS = ("when", "date", "deadline", "period", "cure", "grace", "expire", "expired", "due", "day", "days", "timeline",
               "chronology", "sequence", "before", "after", "late", "notice", "received", "terminat")
_OVERVIEW_WORDS = ("summar", "overview", "what happened", "dispute", "explain", "issues", "problems", "weak", "strong")


def _terms(text: str) -> List[str]:
    words = re.findall(r"[a-z][a-z'\-]+", text.lower())
    out = []
    for word in words:
        if word in _STOP or len(word) < 3:
            continue
        out.append(word[:6])  # crude stem: terminate/termination/terminated -> termin
    return out


def _score(sentence: str, terms: List[str]) -> int:
    low = sentence.lower()
    return sum(1 for term in set(terms) if term in low)


def build_record_answer(query: str, hits: List[Dict[str, Any]], records: List[Dict[str, Any]],
                        timeline: List[Dict[str, Any]], case_title: Optional[str] = None) -> str:
    terms = _terms(query)
    low_query = query.lower()
    wants_dates = any(word in low_query for word in _DATE_WORDS)
    overview = any(word in low_query for word in _OVERVIEW_WORDS) or not terms

    facts = computed_date_facts(records, timeline) if (records or timeline) else ""
    chronology, periods, issues = [], [], []
    section = None
    for line in facts.splitlines():
        if line.startswith("Chronology from the record"):
            section = chronology
        elif line.startswith("Periods and deadlines"):
            section = periods
        elif line.startswith("Issues found by the record checks"):
            section = issues
        elif line.startswith("- ") and section is not None:
            section.append(line[2:])
        else:
            section = None

    def relevant(lines: List[str]) -> List[str]:
        if overview:
            return lines
        ranked = sorted(((_score(line, terms), i, line) for i, line in enumerate(lines)), key=lambda x: (-x[0], x[1]))
        return [line for score, _, line in ranked if score > 0]

    out: List[str] = [HEADER]
    scope = f" in {case_title}" if case_title else ""
    out.append(f"Here is what the record{scope} shows on this question. Each point is quoted or computed from a cited document.")

    picked_periods = periods if (wants_dates or overview) else []
    if picked_periods:
        out.append("**Deadlines computed from the record**")
        out.append("\n".join(f"- {line}" for line in picked_periods))

    picked_issues = relevant(issues)
    if picked_issues:
        out.append("**Points the record checks flagged**")
        out.append("\n".join(f"- {line}" for line in picked_issues))

    quotes: List[str] = []
    seen = set()
    for item in hits or []:
        if item.get("event_type") == "chat":
            continue
        text = str(item.get("text") or "").strip()
        citation = item.get("citation") or item.get("source_name") or "source"
        if not text:
            continue
        # Skip bare labels such as "Exhibit HP-004." that carry no content.
        sentences = [s for s in (_sentences(text) or [text]) if len(s.split()) >= 6] or [text]
        ranked = sorted(sentences, key=lambda s: -_score(s, terms))
        best = [s for s in ranked if _score(s, terms) > 0][:2]
        if not best and overview:
            best = sentences[:1]
        for sentence in best:
            key = sentence.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            quotes.append(f"- “{sentence.strip()}” {citation}")
        if len(quotes) >= 6:
            break
    if quotes:
        out.append("**What the documents say**")
        out.append("\n".join(quotes))

    if (overview or wants_dates) and chronology:
        out.append("**Chronology**")
        out.append("\n".join(f"- {line}" for line in chronology[:12]))

    if len(out) == 2:
        out.append("No document in this matter addresses that question yet. Add the relevant records, or rephrase using "
                   "words that appear in them.")
    out.append("Dates a party asserts in a letter or response are that party's claim, not an established fact. "
               "Legal conclusions remain with counsel.")
    return "\n\n".join(out)
