from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parent
CLAIRE_STATE_DIR = ROOT / "claire_state"
GOLDEN_CORRECTIONS_PATH = CLAIRE_STATE_DIR / "golden_corrections.jsonl"
GOLDEN_TESTS_PATH = CLAIRE_STATE_DIR / "golden_tests.jsonl"


CORRECTION_TYPES = {
    "ROUTING_CORRECTION",
    "TERMINOLOGY_CORRECTION",
    "PRODUCT_POSITIONING_CORRECTION",
    "LEGAL_SAFETY_CORRECTION",
    "NVIDIA_POSITIONING_CORRECTION",
    "LANGUAGE_STYLE_CORRECTION",
    "MEMORY_TRUTH_CORRECTION",
}


def now_ns() -> int:
    return time.time_ns()


def stable_id(*parts: str) -> str:
    payload = "\n".join(part.strip().lower() for part in parts if part).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]


def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                records.append(payload)
    return records


def correction_record(
    *,
    name: str,
    corrected_answer: str,
    inferred_rule: str,
    correction_type: str,
    trigger_terms: Iterable[str],
    must_include: Iterable[str],
    must_not_include: Iterable[str],
    lane_override_if_any: Optional[str] = None,
    confidence: float = 0.85,
    user_id: str = "project",
    session_id: str = "seed",
    original_prompt: str = "",
    wrong_answer_excerpt: str = "",
    active: bool = True,
    timestamp_ns: Optional[int] = None,
) -> Dict[str, Any]:
    if correction_type not in CORRECTION_TYPES:
        raise ValueError(f"unsupported correction_type: {correction_type}")
    correction_id = stable_id(name, inferred_rule, correction_type)
    return {
        "correction_id": correction_id,
        "name": name,
        "timestamp_ns": int(timestamp_ns or now_ns()),
        "user_id": user_id,
        "session_id": session_id,
        "original_prompt": original_prompt,
        "wrong_answer_excerpt": wrong_answer_excerpt[:1000],
        "corrected_answer": corrected_answer.strip(),
        "inferred_rule": inferred_rule.strip(),
        "correction_type": correction_type,
        "trigger_terms": [term for term in trigger_terms if term],
        "must_include": [term for term in must_include if term],
        "must_not_include": [term for term in must_not_include if term],
        "lane_override_if_any": lane_override_if_any,
        "confidence": float(confidence),
        "source": "explicit_user_correction",
        "active": bool(active),
    }


SEEDED_CORRECTIONS: List[Dict[str, Any]] = [
    correction_record(
        name="Veritas Legal routing correction",
        corrected_answer=(
            "Claire Veritas Legal is a guided evidence-intake and case-organization workspace. "
            "It helps organize uploaded documents, photos, notes, dates, communications, expenses, "
            "and related material into source-linked timelines, evidence categories, and attorney-review packets. "
            "It supports legal teams by organizing material for review; it does not provide legal advice, "
            "predict outcomes, or replace attorney judgment."
        ),
        inferred_rule=(
            "If Claire Veritas Legal or Veritas Legal appears with legal, evidence, attorney, case, law office, "
            "litigation, Moss Landing, documents, timeline, or packet context, route to LEGAL_CASE / LEGAL_INTAKE. "
            "Do not route to TRADING_STATION."
        ),
        correction_type="ROUTING_CORRECTION",
        trigger_terms=[
            "Claire Veritas Legal",
            "Veritas Legal",
            "legal evidence",
            "evidence intake",
            "attorney-review packet",
            "law office",
            "Moss Landing",
            "case documents",
            "litigation timeline",
        ],
        must_include=[
            "evidence intake",
            "case organization",
            "timeline",
            "evidence categories",
            "attorney-review packet",
            "not legal advice",
            "does not replace attorneys",
        ],
        must_not_include=[
            "trading",
            "crypto",
            "live trades",
            "broker",
            "Kraken",
            "financial intelligence subsystem",
            "Veritas status requires trusted authority",
        ],
        lane_override_if_any="LEGAL_INTAKE",
        confidence=0.99,
        timestamp_ns=1,
    ),
    correction_record(
        name="Azure NVIDIA infrastructure framing correction",
        corrected_answer=(
            "Read the Azure MLPerf Llama 405B benchmark as market evidence for large-scale AI infrastructure: "
            "Azure and NVIDIA performance depends on topology-aware orchestration, synchronization, and "
            "communication control. Raw model intelligence is not enough. CLAIRE should be framed as governed "
            "runtime infrastructure around models, with ARE providing memory/provenance continuity rather than GPU memory, "
            "and C3RP, Handshake Broker, Diode, Sentinel, and Trace providing runtime governance."
        ),
        inferred_rule=(
            "If the user asks about Azure, NVIDIA, MLPerf, GPUs, topology-aware orchestration, synchronization, "
            "LLM training infrastructure, or large-scale AI systems, answer in the AI infrastructure / NVIDIA pathway frame. "
            "Do not default to OfficeAI-500 unless OfficeAI is specifically asked for. Connect the article to runtime "
            "governance around models."
        ),
        correction_type="NVIDIA_POSITIONING_CORRECTION",
        trigger_terms=[
            "Azure",
            "NVIDIA",
            "MLPerf",
            "Llama 405B",
            "GPUs",
            "topology-aware",
            "synchronization",
            "communication control",
            "NVLink",
            "MRC",
            "large-scale AI infrastructure",
        ],
        must_include=[
            "Azure",
            "NVIDIA",
            "topology-aware orchestration",
            "synchronization",
            "communication control",
            "raw model intelligence is not enough",
            "CLAIRE as governed runtime infrastructure around models",
            "ARE as memory/provenance continuity, not GPU memory",
            "C3RP",
            "Handshake Broker",
            "Diode",
            "Sentinel",
            "Trace",
            "avoid crypto/trading pitch",
        ],
        must_not_include=[
            "Claire Systems trains frontier models",
            "Azure-scale infrastructure claim",
            "crypto",
            "trading bot",
            "gambling bot",
            "OfficeAI-first framing",
        ],
        lane_override_if_any="AI_INFRASTRUCTURE",
        confidence=0.99,
        timestamp_ns=2,
    ),
    correction_record(
        name="ARE terminology correction",
        corrected_answer=(
            "ARE means Analog Recall Engine. In CLAIRE context, ARE refers to governed memory and "
            "chronological/provenance continuity where relevant."
        ),
        inferred_rule="ARE means Analog Recall Engine. Do not define ARE as Agent Runtime Environment.",
        correction_type="TERMINOLOGY_CORRECTION",
        trigger_terms=["ARE", "what does ARE mean", "Analog Recall Engine"],
        must_include=["Analog Recall Engine", "governed memory", "chronological/provenance continuity"],
        must_not_include=["Agent Runtime Environment"],
        lane_override_if_any="PROJECT_TRUTH",
        confidence=0.99,
        timestamp_ns=3,
    ),
]


SEEDED_TESTS: List[Dict[str, Any]] = [
    {
        "name": "Veritas Legal law office explanation",
        "input": "Claire, explain Claire Veritas Legal to a law office employee who has never seen it before.",
        "must_include": SEEDED_CORRECTIONS[0]["must_include"],
        "must_not_include": SEEDED_CORRECTIONS[0]["must_not_include"],
    },
    {
        "name": "Azure NVIDIA infrastructure framing",
        "input": "Claire, analyze this Azure MLPerf Llama 405B benchmark as market evidence for Claire Systems.",
        "must_include": SEEDED_CORRECTIONS[1]["must_include"][:-1],
        "must_not_include": SEEDED_CORRECTIONS[1]["must_not_include"],
    },
    {
        "name": "ARE terminology",
        "input": "Claire, what does ARE mean?",
        "must_include": ["Analog Recall Engine"],
        "must_not_include": ["Agent Runtime Environment"],
    },
]


class CorrectionStore:
    def __init__(
        self,
        corrections_path: Path | str = GOLDEN_CORRECTIONS_PATH,
        tests_path: Path | str = GOLDEN_TESTS_PATH,
    ) -> None:
        self.corrections_path = Path(corrections_path)
        self.tests_path = Path(tests_path)

    def ensure_seed_data(self) -> None:
        existing_ids = {str(item.get("correction_id")) for item in read_jsonl(self.corrections_path)}
        for record in SEEDED_CORRECTIONS:
            if record["correction_id"] not in existing_ids:
                append_jsonl(self.corrections_path, record)
        existing_test_names = {str(item.get("name")) for item in read_jsonl(self.tests_path)}
        for record in SEEDED_TESTS:
            if record["name"] not in existing_test_names:
                append_jsonl(self.tests_path, record)

    def list_corrections(self, *, active_only: bool = True) -> List[Dict[str, Any]]:
        self.ensure_seed_data()
        records = read_jsonl(self.corrections_path)
        if active_only:
            records = [record for record in records if record.get("active") is True]
        return records

    def save_correction(self, record: Dict[str, Any]) -> Dict[str, Any]:
        required = {
            "correction_id",
            "timestamp_ns",
            "user_id",
            "session_id",
            "original_prompt",
            "wrong_answer_excerpt",
            "corrected_answer",
            "inferred_rule",
            "correction_type",
            "trigger_terms",
            "must_include",
            "must_not_include",
            "lane_override_if_any",
            "confidence",
            "source",
            "active",
        }
        missing = required - set(record)
        if missing:
            raise ValueError(f"correction missing fields: {sorted(missing)}")
        self.ensure_seed_data()
        append_jsonl(self.corrections_path, record)
        return record

    def save_golden_test(self, record: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure_seed_data()
        append_jsonl(self.tests_path, record)
        return record

