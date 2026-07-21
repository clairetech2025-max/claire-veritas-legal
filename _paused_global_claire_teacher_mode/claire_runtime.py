from __future__ import annotations

from typing import Dict, Optional

from correction_learning import matching_corrections
from correction_store import CorrectionStore
from lane_classifier import classify_lane


def _legal_veritas_answer() -> str:
    return (
        "Claire Veritas Legal is a guided evidence intake and case organization workspace. "
        "It helps organize uploaded documents, photos, notes, dates, communications, expenses, and related material "
        "into source-linked timeline views, evidence categories, and attorney-review packet materials. "
        "It supports legal teams by organizing material for review; it is not legal advice, does not predict outcomes, "
        "and does not replace attorneys or attorney judgment."
    )


def _azure_nvidia_answer() -> str:
    return (
        "The Azure MLPerf Llama 405B benchmark is market evidence that large-scale AI infrastructure depends on "
        "Azure and NVIDIA working through topology-aware orchestration, synchronization, and communication control. "
        "Raw model intelligence is not enough; production systems need governed runtime infrastructure around models. "
        "CLAIRE should be framed as governed runtime around models, where ARE is memory/provenance continuity, not GPU memory. "
        "C3RP, Handshake Broker, Diode, Sentinel, and Trace are the runtime governance layer that keeps model use controlled, "
        "auditable, and connected to provenance."
    )


def _are_answer() -> str:
    return (
        "ARE means Analog Recall Engine. In CLAIRE, ARE refers to governed memory and chronological/provenance continuity "
        "where relevant."
    )


def answer_from_corrections(prompt: str, *, store: Optional[CorrectionStore] = None) -> Optional[str]:
    matches = matching_corrections(prompt, store=store)
    if not matches:
        return None
    first = matches[0]
    name = str(first.get("name", "")).lower()
    correction_type = str(first.get("correction_type", ""))
    if "veritas legal" in name:
        return _legal_veritas_answer()
    if correction_type == "NVIDIA_POSITIONING_CORRECTION":
        return _azure_nvidia_answer()
    if correction_type == "TERMINOLOGY_CORRECTION":
        return _are_answer()
    corrected = str(first.get("corrected_answer") or "").strip()
    return corrected or None


def answer(prompt: str, *, store: Optional[CorrectionStore] = None) -> Dict[str, object]:
    target = store or CorrectionStore()
    lane = classify_lane(prompt, store=target)
    corrected_answer = answer_from_corrections(prompt, store=target)
    return {
        "answer": corrected_answer,
        "lane": lane["lane"],
        "source": "explicit_correction" if corrected_answer else "runtime",
        "corrections": lane.get("corrections", []),
    }

