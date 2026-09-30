"""Dated events pulled from the record, for the matter chronology.

Every event is a sentence from a source document that contains a calendar
date. The first date in the sentence places the event; any other dates in the
same sentence are kept as "also mentions" so the attorney sees competing dates
(for example a claimed receipt date) without the system choosing between them.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_MONTH_NAME = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
    r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_DATE_RE = re.compile(
    rf"\b(?P<md>(?P<m1>{_MONTH_NAME})\.?\s+(?P<d1>\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(?P<y1>(?:19|20)\d{{2}}))?)\b"
    rf"|\b(?P<dm>(?P<d2>\d{{1,2}})\s+(?P<m2>{_MONTH_NAME})\.?,?\s+(?P<y2>(?:19|20)\d{{2}}))\b"
    r"|\b(?P<iso>(?P<y3>(?:19|20)\d{2})-(?P<m3>\d{1,2})-(?P<d3>\d{1,2}))\b"
    r"|\b(?P<us>(?P<m4>\d{1,2})/(?P<d4>\d{1,2})/(?P<y4>(?:19|20)?\d{2}))\b",
    re.IGNORECASE,
)
_ABBREVIATIONS = ("a.m.", "p.m.", "inc.", "no.", "co.", "corp.", "ltd.", "llc.", "v.", "vs.", "mr.", "ms.", "mrs.", "dr.", "st.", "sec.")
_SENTENCE_END = re.compile(r"(?<=[.!?])[\"')\]]?\s+(?=[\"'(\[]?[A-Z0-9])")


def _sentences(text: str) -> List[str]:
    pieces = _SENTENCE_END.split(" ".join(str(text or "").split()))
    merged: List[str] = []
    for piece in pieces:
        if merged and (
            merged[-1].lower().endswith(_ABBREVIATIONS)
            or re.search(rf"\b{_MONTH_NAME}\.$", merged[-1], re.IGNORECASE)
        ):
            merged[-1] = f"{merged[-1]} {piece}"
        else:
            merged.append(piece)
    return [piece.strip() for piece in merged if piece.strip()]


def _month(value: str) -> int:
    return _MONTHS[value.lower()[:3]]


def _parse(match: re.Match) -> Tuple[Optional[int], int, int]:
    """Return (year or None, month, day) for one date match."""
    if match.group("md"):
        year = match.group("y1")
        return (int(year) if year else None, _month(match.group("m1")), int(match.group("d1")))
    if match.group("dm"):
        return (int(match.group("y2")), _month(match.group("m2")), int(match.group("d2")))
    if match.group("iso"):
        return (int(match.group("y3")), int(match.group("m3")), int(match.group("d3")))
    year = int(match.group("y4"))
    if year < 100:
        year += 2000
    return (year, int(match.group("m4")), int(match.group("d4")))


def _as_date(year: Optional[int], month: int, day: int) -> Optional[date]:
    if year is None:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def date_label(value: date) -> str:
    return f"{value.strftime('%b')} {value.day}, {value.year}"


def dated_events(text: str) -> List[Dict[str, Any]]:
    """Sentences in ``text`` that carry a date, in document order.

    A date written without a year ("on April 3") takes the year of the nearest
    full date before it in the same document, or the first full date after it,
    and is marked ``year_inferred``. Dates whose year cannot be inferred are
    left out rather than guessed.
    """
    sentences = _sentences(text)
    full_years = [
        (index, year)
        for index, sentence in enumerate(sentences)
        for match in _DATE_RE.finditer(sentence)
        for year, _month_value, _day in [_parse(match)]
        if year is not None
    ]

    def infer_year(index: int) -> Optional[int]:
        before = [year for position, year in full_years if position <= index]
        if before:
            return before[-1]
        after = [year for position, year in full_years if position > index]
        return after[0] if after else None

    events: List[Dict[str, Any]] = []
    for index, sentence in enumerate(sentences):
        found = []
        last_year: Optional[int] = None
        for match in _DATE_RE.finditer(sentence):
            year, month, day = _parse(match)
            inferred = False
            if year is None:
                year = last_year or infer_year(index)
                inferred = year is not None
            else:
                last_year = year
            when = _as_date(year, month, day)
            if when is not None:
                found.append({"date": when, "text": match.group(0), "year_inferred": inferred})
        if not found:
            continue
        first, others = found[0], found[1:]
        events.append({
            "event_date": first["date"].isoformat(),
            "date_label": date_label(first["date"]),
            "date_text": first["text"],
            "year_inferred": first["year_inferred"],
            "also_mentions": [
                {"event_date": item["date"].isoformat(), "date_label": date_label(item["date"]), "year_inferred": item["year_inferred"]}
                for item in others
                if item["date"] != first["date"]
            ],
            "sentence": sentence,
        })
    return events
