from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from correction_store import CorrectionStore, correction_record
from sentinel_validator import validate_correction_safety


TRIGGER_PHRASES = [
    "Claire, correction:",
    "Correction:",
    "That was wrong. Correct answer is",
    "This is the correct response",
    "You should have said",
    "Save this as a correction",
    "Remember this correction",
]


LEGAL_CONTEXT_TERMS = {
    "legal",
    "evidence",
    "attorney",
    "case",
    "law office",
    "litigation",
    "moss landing",
    "documents",
    "timeline",
    "packet",
}


def detect_correction(text: str) -> Optional[List[str]]:
    lowered = text.lower()
    matched = [trigger for trigger in TRIGGER_PHRASES if trigger.lower() in lowered]
    return matched or None


def _after_first_trigger(text: str, triggers: Iterable[str]) -> str:
    positions = []
    lowered = text.lower()
    for trigger in triggers:
        index = lowered.find(trigger.lower())
        if index >= 0:
            positions.append((index, len(trigger)))
    if not positions:
        return text.strip()
    index, length = sorted(positions)[0]
    return text[index + length :].strip(" :-\n\t")


def _terms_from_text(text: str) -> List[str]:
    known_terms = [
        "Claire Veritas Legal",
        "Veritas Legal",
        "legal evidence",
        "evidence intake",
        "attorney-review packet",
        "law office",
        "Moss Landing",
        "Azure",
        "NVIDIA",
        "MLPerf",
        "Llama 405B",
        "GPUs",
        "topology-aware",
        "synchronization",
        "communication control",
        "ARE",
        "Analog Recall Engine",
    ]
    found = [term for term in known_terms if term.lower() in text.lower()]
    quoted = re.findall(r'"([^"]{2,80})"', text)
    for item in quoted:
        if item not in found:
            found.append(item)
    return found[:16]


def classify_correction(text: str) -> str:
    lowered = text.lower()
    if "legal advice" in lowered or "attorney" in lowered:
        return "LEGAL_SAFETY_CORRECTION" if "advice" in lowered else "ROUTING_CORRECTION"
    if "azure" in lowered or "nvidia" in lowered or "mlperf" in lowered:
        return "NVIDIA_POSITIONING_CORRECTION"
    if "are" in lowered or "mean" in lowered or "terminology" in lowered:
        return "TERMINOLOGY_CORRECTION"
    if "route" in lowered or "veritas legal" in lowered:
        return "ROUTING_CORRECTION"
    if "style" in lowered or "tone" in lowered:
        return "LANGUAGE_STYLE_CORRECTION"
    if "remember" in lowered or "truth" in lowered:
        return "MEMORY_TRUTH_CORRECTION"
    return "PRODUCT_POSITIONING_CORRECTION"


def infer_rule(corrected_answer: str, correction_type: str) -> str:
    lowered = corrected_answer.lower()
    if "veritas legal" in lowered and ("trading" in lowered or "evidence intake" in lowered):
        return "When Veritas Legal is used in legal or evidence context, route to LEGAL_INTAKE and do not answer from trading context."
    if "are" in lowered and "analog recall engine" in lowered:
        return "ARE means Analog Recall Engine. Do not define ARE as Agent Runtime Environment."
    if "azure" in lowered or "nvidia" in lowered or "mlperf" in lowered:
        return "Answer Azure, NVIDIA, MLPerf, GPU, and large-scale AI infrastructure prompts in the AI infrastructure pathway frame."
    if correction_type == "LEGAL_SAFETY_CORRECTION":
        return "Preserve legal safety boundaries and attorney-review framing."
    return f"Apply this {correction_type.lower()} as a durable project rule rather than as one chat memory."


def infer_must_include(corrected_answer: str, correction_type: str) -> List[str]:
    lowered = corrected_answer.lower()
    if "veritas legal" in lowered or "evidence intake" in lowered:
        return ["evidence intake", "case organization"]
    if "analog recall engine" in lowered:
        return ["Analog Recall Engine"]
    if correction_type == "NVIDIA_POSITIONING_CORRECTION":
        return ["Azure", "NVIDIA"]
    return []


def infer_must_not_include(corrected_answer: str, correction_type: str) -> List[str]:
    lowered = corrected_answer.lower()
    blocked: List[str] = []
    if "do not talk about trading" in lowered or "not trading" in lowered or "veritas legal" in lowered:
        blocked.extend(["trading", "crypto", "live trades", "broker"])
    if "agent runtime environment" in lowered and "do not" in lowered:
        blocked.append("Agent Runtime Environment")
    if correction_type == "NVIDIA_POSITIONING_CORRECTION":
        blocked.extend(["OfficeAI-first framing", "crypto", "trading bot"])
    return blocked


def infer_lane(corrected_answer: str, correction_type: str) -> Optional[str]:
    lowered = corrected_answer.lower()
    if "veritas legal" in lowered or "evidence intake" in lowered:
        return "LEGAL_INTAKE"
    if correction_type == "NVIDIA_POSITIONING_CORRECTION":
        return "AI_INFRASTRUCTURE"
    if correction_type == "TERMINOLOGY_CORRECTION":
        return "PROJECT_TRUTH"
    return None


def learn_from_correction(
    text: str,
    *,
    original_prompt: str = "",
    wrong_answer_excerpt: str = "",
    user_id: str = "local_user",
    session_id: str = "local_session",
    store: Optional[CorrectionStore] = None,
) -> Dict[str, Any]:
    triggers = detect_correction(text)
    if not triggers:
        return {"detected": False}
    corrected_answer = _after_first_trigger(text, triggers)
    is_safe, reasons = validate_correction_safety(corrected_answer)
    if not is_safe:
        return {
            "detected": True,
            "saved": False,
            "active": False,
            "reasons": reasons,
            "reply": "I cannot save that as an active correction because it would weaken legal safety, secrecy, auditability, or attorney-review boundaries.",
        }
    correction_type = classify_correction(corrected_answer)
    rule = infer_rule(corrected_answer, correction_type)
    record = correction_record(
        name=rule[:80],
        corrected_answer=corrected_answer,
        inferred_rule=rule,
        correction_type=correction_type,
        trigger_terms=_terms_from_text(corrected_answer),
        must_include=infer_must_include(corrected_answer, correction_type),
        must_not_include=infer_must_not_include(corrected_answer, correction_type),
        lane_override_if_any=infer_lane(corrected_answer, correction_type),
        confidence=0.76,
        user_id=user_id,
        session_id=session_id,
        original_prompt=original_prompt,
        wrong_answer_excerpt=wrong_answer_excerpt,
        active=True,
    )
    target = store or CorrectionStore()
    target.save_correction(record)
    if record["confidence"] >= 0.75 and record["trigger_terms"]:
        target.save_golden_test(
            {
                "name": record["name"],
                "input": original_prompt or ", ".join(record["trigger_terms"]),
                "must_include": record["must_include"],
                "must_not_include": record["must_not_include"],
                "source_correction_id": record["correction_id"],
            }
        )
    return {
        "detected": True,
        "saved": True,
        "active": True,
        "record": record,
        "reply": f"Understood. I saved this as a correction rule: {rule} I will apply it before future routing and answer generation.",
    }


def correction_matches_prompt(correction: Dict[str, Any], prompt: str) -> bool:
    lowered = prompt.lower()
    terms = [str(term).lower() for term in correction.get("trigger_terms", []) if str(term).strip()]
    if not terms:
        return False
    if str(correction.get("name", "")).lower().startswith("veritas legal"):
        has_veritas = "veritas legal" in lowered or "claire veritas legal" in lowered
        has_legal_context = any(term in lowered for term in LEGAL_CONTEXT_TERMS)
        return has_veritas and has_legal_context
    if str(correction.get("correction_type")) == "TERMINOLOGY_CORRECTION":
        return "are" in lowered and ("mean" in lowered or "what does" in lowered or "define" in lowered)
    hits = sum(1 for term in terms if term in lowered)
    return hits >= 1 if len(terms) <= 3 else hits >= 2


def matching_corrections(prompt: str, store: Optional[CorrectionStore] = None) -> List[Dict[str, Any]]:
    target = store or CorrectionStore()
    return [record for record in target.list_corrections(active_only=True) if correction_matches_prompt(record, prompt)]


def correction_context(prompt: str, store: Optional[CorrectionStore] = None) -> str:
    matches = matching_corrections(prompt, store=store)
    if not matches:
        return ""
    lines = ["High-priority explicit correction rules. Apply before stale memory, keyword routing, and answer generation."]
    for record in matches[:3]:
        lines.append(f"- Rule: {record.get('inferred_rule')}")
        if record.get("lane_override_if_any"):
            lines.append(f"  Lane override: {record.get('lane_override_if_any')}")
        if record.get("must_include"):
            lines.append("  Must include: " + ", ".join(record.get("must_include", [])))
        if record.get("must_not_include"):
            lines.append("  Must not include: " + ", ".join(record.get("must_not_include", [])))
    return "\n".join(lines)

