"""Issues found in the record by explicit checks, never by keyword spotting.

Each issue names the sentences it relies on and shows its arithmetic, so an
attorney can verify it in a minute. Dates are computed here, not by the model.
The checks only flag; they never decide which side's reading is correct.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .chronology import _sentences, date_label

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "fourteen": 14, "fifteen": 15, "twenty": 20, "thirty": 30,
    "forty-five": 45, "sixty": 60, "ninety": 90,
}
_PERIOD_RE = re.compile(
    r"\b(?P<n>\d{1,3}|" + "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True)) + r")"
    r"(?:\s*\(\d{1,3}\))?[\s-]+(?P<kind>business|calendar|court)?[\s-]*days?\b",
    re.IGNORECASE,
)
_PERIOD_PURPOSE = {
    "cure": re.compile(r"\bcure\b", re.IGNORECASE),
    "grace": re.compile(r"\bgrace\b", re.IGNORECASE),
}
_NOTICE_RE = re.compile(r"\b(notice|default|delivered|delivery|received|receipt|served)\b", re.IGNORECASE)
_TERMINATION_RE = re.compile(r"\bterminat", re.IGNORECASE)
# An act of termination, not a threat, a plan, or a later dispute about one.
_TERMINATED_RE = re.compile(
    r"\bterminated\b|\btermination (?:letter|notice)\s+(?:was\s+)?(?:dated|sent|issued|delivered)\b",
    re.IGNORECASE,
)
# Someone acting toward termination (as opposed to a contract clause about it).
_STEP_RE = re.compile(r"\b(?:authori[sz]\w*|prepar\w*|decided|drafted|approved|resolved|voted)\b", re.IGNORECASE)
_CONTESTED_RE = re.compile(
    r"\b(disputes?|disputed|contests?|contested|denies|denied|could not have|never received|"
    r"was not received|not received until|objects? to|rejects?)\b",
    re.IGNORECASE,
)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    last = (date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def federal_holidays(year: int) -> Dict[date, str]:
    """United States federal holidays (5 U.S.C. 6103), with weekend observance."""
    fixed = {
        "New Year's Day": date(year, 1, 1),
        "Juneteenth": date(year, 6, 19),
        "Independence Day": date(year, 7, 4),
        "Veterans Day": date(year, 11, 11),
        "Christmas Day": date(year, 12, 25),
    }
    holidays = {_observed(day): name for name, day in fixed.items()}
    holidays.update({
        _nth_weekday(year, 1, 0, 3): "Martin Luther King Jr. Day",
        _nth_weekday(year, 2, 0, 3): "Presidents' Day",
        _last_weekday(year, 5, 0): "Memorial Day",
        _nth_weekday(year, 9, 0, 1): "Labor Day",
        _nth_weekday(year, 10, 0, 2): "Columbus Day",
        _nth_weekday(year, 11, 3, 4): "Thanksgiving Day",
    })
    return holidays


def add_days(start: date, count: int, *, business: bool, skip_holidays: bool = False) -> date:
    """The last day of a period of ``count`` days that begins the day after ``start``."""
    if not business:
        return start + timedelta(days=count)
    day, counted = start, 0
    while counted < count:
        day += timedelta(days=1)
        if day.weekday() >= 5:
            continue
        if skip_holidays and day in federal_holidays(day.year):
            continue
        counted += 1
    return day


def _holidays_between(start: date, end: date) -> List[Tuple[date, str]]:
    found = []
    for year in range(start.year, end.year + 1):
        for day, name in federal_holidays(year).items():
            if start < day <= end and day.weekday() < 5:
                found.append((day, name))
    return sorted(found)


def _record_label(record: Dict[str, Any]) -> str:
    name = str(record.get("source_name") or record.get("title") or "record")
    return re.sub(r"\.(txt|md|pdf|docx?|jsonl?|csv)$", "", name, flags=re.IGNORECASE)


def find_periods(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Cure and grace periods stated in the record, with the sentence and source."""
    periods: List[Dict[str, Any]] = []
    seen = set()
    for record in records:
        for sentence in _sentences(str(record.get("text") or record.get("summary") or "")):
            for purpose, purpose_re in _PERIOD_PURPOSE.items():
                if not purpose_re.search(sentence):
                    continue
                match = _PERIOD_RE.search(sentence)
                if not match:
                    continue
                raw = match.group("n").lower()
                count = int(raw) if raw.isdigit() else _NUMBER_WORDS[raw]
                business = (match.group("kind") or "").lower() in {"business", "court"}
                periods.append({
                    "purpose": purpose, "days": count, "business": business,
                    "phrase": match.group(0), "sentence": sentence,
                    "source": _record_label(record), "citation": record.get("citation") or f"[{record.get('source_name', 'source')}]",
                })
    governing = re.compile(r"\b(agreement|contract|lease|section|clause|provides|requires)\b", re.IGNORECASE)
    periods.sort(key=lambda period: not governing.search(period["sentence"]))
    return periods


def _event_dates(item: Dict[str, Any]) -> List[date]:
    dates = [date.fromisoformat(item["event_date"])] if item.get("event_date") else []
    dates += [date.fromisoformat(m["event_date"]) for m in item.get("also_mentions") or []]
    return dates


def _describe_period(period: Dict[str, Any]) -> str:
    unit = "business-day" if period["business"] else "calendar-day"
    return f"{period['days']}-{unit} {period['purpose']} period"


def find_issues(records: List[Dict[str, Any]], timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    dated = [item for item in timeline if item.get("dated") and item.get("event_date")]
    issues: List[Dict[str, Any]] = []

    cure_periods = [p for p in find_periods(records) if p["purpose"] == "cure"]
    notices: Dict[date, Dict[str, Any]] = {}
    for item in dated:
        if _NOTICE_RE.search(item["summary"]) and not _TERMINATION_RE.search(item["summary"]):
            for when in _event_dates(item):
                notices.setdefault(when, item)
    contested = [item for item in dated if _CONTESTED_RE.search(item["summary"])]
    terminations = [item for item in dated if _TERMINATION_RE.search(item["summary"]) and item not in contested]
    acts: Dict[date, Dict[str, Any]] = {}
    for item in terminations:
        if _TERMINATED_RE.search(item["summary"]):
            acts.setdefault(date.fromisoformat(item["event_date"]), item)

    for period in cure_periods[:1]:
        starts = sorted(notices)
        if not starts:
            continue
        for act_day, act in sorted(acts.items()):
            ends = [(start, add_days(start, period["days"], business=period["business"])) for start in starts if start < act_day]
            open_ends = [(start, end) for start, end in ends if act_day <= end]
            if not open_ends:
                continue
            counting = "; ".join(
                f"counting from {date_label(start)} ({notices[start]['title']}) it ends {date_label(end)}"
                for start, end in open_ends
            )
            holidays = _holidays_between(open_ends[0][0], max(end for _, end in open_ends))
            holiday_note = ""
            if holidays and period["business"]:
                shifted = "; ".join(
                    f"{date_label(add_days(start, period['days'], business=True, skip_holidays=True))} from {date_label(start)}"
                    for start, _ in open_ends
                )
                holiday_note = (
                    f" {holidays[0][1]} ({date_label(holidays[0][0])}), a federal holiday, falls inside the period; if the agreement does "
                    f"not treat it as a business day, the period ends {shifted}."
                )
            issues.append({
                "label": "deadline conflict",
                "kind": "Deadline",
                "summary": (
                    f"{act['title']} is dated {date_label(act_day)}, before the {_describe_period(period)} "
                    f"({period['source']}) had run: {counting}.{holiday_note} Counsel should confirm which date starts the period."
                ),
                "citations": [period["citation"], act["citation"]] + [notices[start]["citation"] for start, _ in open_ends],
            })

    steps = [item for item in terminations if _STEP_RE.search(item["summary"]) or _TERMINATED_RE.search(item["summary"])]
    if notices and steps:
        first_notice = min(notices)
        for item in steps:
            when = date.fromisoformat(item["event_date"])
            if when < first_notice:
                issues.append({
                    "label": "sequence issue",
                    "kind": "Sequence",
                    "summary": (
                        f"{item['title']} ({date_label(when)}) records a termination step before the first notice "
                        f"in the record ({date_label(first_notice)}, {notices[first_notice]['title']}): \"{item['summary'][:220]}\""
                    ),
                    "citations": [item["citation"], notices[first_notice]["citation"]],
                })

    for item in contested:
        issues.append({
            "label": "contested fact",
            "kind": "Contested",
            "summary": f"{item['title']} ({item['date_label']}) disputes the record: \"{item['summary'][:260]}\"",
            "citations": [item["citation"]],
        })
    return issues
