from __future__ import annotations

from typing import Dict, Iterable, List, Tuple


UNSAFE_CORRECTION_PATTERNS = {
    "permit legal advice as final advice": [
        "final legal advice",
        "tell me i will win",
        "guarantee i will win",
        "legal conclusion",
        "replace attorney",
    ],
    "permit live trading": ["live trading", "place trades", "execute trades", "trade for me"],
    "expose secrets": ["show api key", "expose secrets", "print secrets", "passphrase"],
    "disable safety boundaries": ["disable safety", "ignore safety", "bypass safety", "no guardrails"],
    "erase auditability": ["erase audit", "delete trace", "no trace", "hide provenance"],
    "bypass attorney review": ["bypass attorney", "no attorney review", "skip attorney review"],
    "route private legal materials into public output": ["public output", "publish private legal", "leak legal"],
}


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    haystack = text.lower()
    return any(needle in haystack for needle in needles)


def validate_correction_safety(text: str) -> Tuple[bool, List[str]]:
    reasons = [reason for reason, patterns in UNSAFE_CORRECTION_PATTERNS.items() if _contains_any(text, patterns)]
    return (not reasons, reasons)


def validate_answer_against_correction(answer: str, correction: Dict[str, object]) -> Dict[str, object]:
    text = answer.lower()
    missing = [term for term in correction.get("must_include", []) if str(term).lower() not in text]
    forbidden = [term for term in correction.get("must_not_include", []) if str(term).lower() in text]
    return {"ok": not missing and not forbidden, "missing": missing, "forbidden": forbidden}

