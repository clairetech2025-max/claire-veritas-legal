from __future__ import annotations

import hashlib
import time
from pathlib import Path
from typing import Any

from memory_io import append_jsonl, read_jsonl
from veritas_workflow_guard import evidence_handling_rules


TRIGGER_PHRASES = [
    "claire, correction:",
    "correction:",
    "that was wrong. correct answer is",
    "this is the correct response",
    "you should have said",
    "save this as a correction",
    "remember this correction",
]

UNSAFE_CORRECTION_MARKERS = [
    "final legal advice",
    "tell me i will win",
    "guarantee we win",
    "delete trace",
    "erase audit",
    "bypass attorney review",
    "ignore sources",
    "ignore evidence",
    "publish private",
    "public output",
]


def correction_store_path(root: Path) -> Path:
    return root / "memory" / "veritas_corrections.jsonl"


def detect_teacher_mode(text: str) -> list[str]:
    lowered = str(text or "").lower()
    return [phrase for phrase in TRIGGER_PHRASES if phrase in lowered]


def _after_trigger(text: str, triggers: list[str]) -> str:
    lowered = text.lower()
    matches = [(lowered.find(trigger), len(trigger)) for trigger in triggers if lowered.find(trigger) >= 0]
    if not matches:
        return text.strip()
    index, length = sorted(matches)[0]
    return text[index + length :].strip(" :-\n\t")


def _stable_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _infer_type(text: str) -> str:
    lowered = text.lower()
    if "bias" in lowered or "neutral" in lowered or "one-sided" in lowered:
        return "BIAS_CORRECTION"
    if "evidence" in lowered or "source" in lowered or "citation" in lowered:
        return "EVIDENCE_HANDLING_CORRECTION"
    if "packet" in lowered or "timeline" in lowered or "workflow" in lowered:
        return "WORKFLOW_CORRECTION"
    if "legal advice" in lowered or "attorney" in lowered:
        return "LEGAL_SAFETY_CORRECTION"
    return "PRODUCT_GUIDANCE_CORRECTION"


def _infer_rule(corrected: str, correction_type: str) -> str:
    lowered = corrected.lower()
    if "veritas legal" in lowered or "legal evidence intake" in lowered:
        return "Treat Veritas Legal as legal evidence intake, case organization, timeline, and attorney-review packet support."
    if "do not" in lowered:
        return corrected[:240]
    if correction_type == "EVIDENCE_HANDLING_CORRECTION":
        return "Prefer source-linked evidence handling and distinguish original evidence from derived notes or OCR."
    if correction_type == "BIAS_CORRECTION":
        return "Use neutral, source-linked language and avoid unsupported credibility or outcome assumptions."
    return "Apply this Veritas Legal product correction before workflow guidance and answer generation."


def handle_teacher_mode(
    text: str,
    *,
    root: Path,
    user_id: str = "local_user",
    session_id: str = "local_session",
    original_prompt: str = "",
    wrong_answer_excerpt: str = "",
) -> dict[str, Any]:
    triggers = detect_teacher_mode(text)
    if not triggers:
        return {"detected": False}

    corrected = _after_trigger(text, triggers)
    lowered = corrected.lower()
    unsafe = [marker for marker in UNSAFE_CORRECTION_MARKERS if marker in lowered]
    if unsafe:
        return {
            "detected": True,
            "saved": False,
            "active": False,
            "reasons": unsafe,
            "reply": "I cannot save that as an active Veritas Legal correction because it would weaken legal safety, source integrity, auditability, or attorney review.",
        }

    correction_type = _infer_type(corrected)
    rule = _infer_rule(corrected, correction_type)
    record = {
        "correction_id": _stable_id(rule + corrected),
        "timestamp_ns": time.time_ns(),
        "user_id": user_id,
        "session_id": session_id,
        "original_prompt": original_prompt,
        "wrong_answer_excerpt": wrong_answer_excerpt[:1000],
        "corrected_answer": corrected,
        "inferred_rule": rule,
        "correction_type": correction_type,
        "scope": "veritas_legal_product",
        "evidence_rules": evidence_handling_rules(),
        "source": "explicit_user_correction",
        "active": True,
    }
    append_jsonl(str(correction_store_path(root)), record)
    return {
        "detected": True,
        "saved": True,
        "active": True,
        "record": record,
        "reply": f"Understood. I saved this as a Veritas Legal correction rule: {rule} I will apply it before future workflow guidance and answer generation.",
    }


def active_correction_rules(root: Path, limit: int = 8) -> list[dict[str, Any]]:
    records = [record for record in read_jsonl(str(correction_store_path(root))) if record.get("active") is True]
    return records[-max(0, int(limit)) :]

