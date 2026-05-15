from __future__ import annotations

import base64
import io
import json
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from memory_io import _ts, append_jsonl, read_jsonl
from .legal_intel import (
    build_exhibit_index,
    build_filing_packet,
    default_matter,
    detect_anomalies,
    estimate_billing,
    get_court_profile,
    list_court_profiles,
    list_filing_templates,
    rank_scenarios,
)

try:
    import palantir_parser as legacy_parser  # type: ignore
except Exception:  # pragma: no cover - optional legacy helper
    legacy_parser = None

try:
    import docx  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    docx = None

try:
    import PyPDF2  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    PyPDF2 = None

try:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    pytesseract = None
    Image = None


SEMANTIC_WEIGHT = 0.40
TEMPORAL_WEIGHT = 0.20
INTENT_WEIGHT = 0.25
PRIORITY_WEIGHT = 0.15

DEFAULT_PRIORITY = 0.50
MAX_TEMPORAL_AGE_SECONDS = 60 * 60 * 24 * 14

LEGAL_INTENT_KEYWORDS = {
    "case": {"case", "docket", "complaint", "petition", "motion", "order"},
    "evidence": {"evidence", "exhibit", "document", "proof", "record", "discovery"},
    "timeline": {"timeline", "chronology", "sequence", "dated", "timestamp"},
    "ocr": {"ocr", "scan", "image", "photo", "video", "frame"},
    "research": {"research", "authority", "citation", "precedent", "statute"},
    "chat": {"chat", "answer", "question", "analysis", "summary"},
    "ingest": {"ingest", "upload", "import", "load", "parse"},
}


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def slugify(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return value or "unassigned"


def tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def strip_html(text: str) -> str:
    text = re.sub(r"(?is)<script.*?>.*?</script>", " ", text or "")
    text = re.sub(r"(?is)<style.*?>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> List[str]:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def intent_tags(text: str) -> List[str]:
    tokens = set(tokenize(text))
    tags = [tag for tag, words in LEGAL_INTENT_KEYWORDS.items() if tokens.intersection(words)]
    return tags or ["chat"]


def intent_overlap(query_tags: List[str], item_tags: List[str]) -> float:
    q = set(query_tags or ["chat"])
    i = set(item_tags or ["chat"])
    if not q or not i:
        return 0.0
    return len(q.intersection(i)) / max(1, len(q.union(i)))


def temporal_score(timestamp: float, now: Optional[float] = None) -> float:
    now = now or time.time()
    age = max(0.0, now - float(timestamp or now))
    return clamp01(1.0 - (age / MAX_TEMPORAL_AGE_SECONDS))


def final_weighted_score(semantic: float, temporal: float, intent: float, priority: float) -> float:
    return clamp01(
        (SEMANTIC_WEIGHT * semantic)
        + (TEMPORAL_WEIGHT * temporal)
        + (INTENT_WEIGHT * intent)
        + (PRIORITY_WEIGHT * priority)
    )


def semantic_score(query: str, text: str) -> float:
    q_tokens = tokenize(query)
    if not q_tokens:
        return 0.0
    t_tokens = Counter(tokenize(text))
    shared = sum(min(1, t_tokens.get(tok, 0)) for tok in set(q_tokens))
    return clamp01(shared / max(1, len(set(q_tokens))))


@dataclass
class MemoryHit:
    item: Dict[str, Any]
    semantic_score: float
    temporal_score: float
    intent_score: float
    priority_score: float
    final_score: float

    def as_dict(self) -> Dict[str, Any]:
        payload = dict(self.item)
        payload.update(
            {
                "semantic_score": round(self.semantic_score, 6),
                "temporal_score": round(self.temporal_score, 6),
                "intent_score": round(self.intent_score, 6),
                "priority_score": round(self.priority_score, 6),
                "final_score": round(self.final_score, 6),
            }
        )
        return payload


class WorkspaceStore:
    def __init__(self, root: Path):
        self.root = root
        self.memory_dir = root / "memory"
        self.knowledge_dir = root / "knowledge"
        self.vault_dir = root / "vault" / "veritas_legal"
        self.upload_dir = self.vault_dir / "uploads"
        self.runtime_dir = self.root / "web" / "runtime"
        self.documents_path = self.memory_dir / "veritas_documents.jsonl"
        self.cases_path = self.memory_dir / "veritas_cases.jsonl"
        self.matters_path = self.memory_dir / "veritas_matters.jsonl"
        self.traces_path = self.memory_dir / "veritas_traces.jsonl"
        self.evidence_path = self.memory_dir / "veritas_evidence.jsonl"
        self.filings_path = self.memory_dir / "veritas_filings.jsonl"
        self.cache_path = self.memory_dir / "veritas_cache.jsonl"
        self._cache: List[Dict[str, Any]] = []
        self._gyro_recent: List[Dict[str, Any]] = []
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        for path in [self.memory_dir, self.knowledge_dir, self.vault_dir, self.upload_dir, self.runtime_dir]:
            path.mkdir(parents=True, exist_ok=True)

    def _legacy_memory_paths(self) -> List[Tuple[Path, str]]:
        return [
            (self.memory_dir / "qa_overrides.jsonl", "qa_override"),
            (self.memory_dir / "facts.jsonl", "fact"),
            (self.memory_dir / "blocks.jsonl", "block"),
            (self.memory_dir / "pins.jsonl", "pin"),
        ]

    def _record_case(self, case_id: str, title: Optional[str], status: str = "active") -> Dict[str, Any]:
        now = time.time()
        record = {
            "case_id": case_id,
            "title": title or case_id.replace("-", " ").title(),
            "status": status,
            "priority": DEFAULT_PRIORITY,
            "created_at": now,
            "updated_at": now,
            "tags": intent_tags(title or case_id),
        }
        append_jsonl(str(self.cases_path), record)
        return record

    def _record_document(self, record: Dict[str, Any]) -> None:
        append_jsonl(str(self.documents_path), record)

    def _record_trace(self, record: Dict[str, Any]) -> None:
        append_jsonl(str(self.traces_path), record)

    def _record_evidence(self, record: Dict[str, Any]) -> None:
        append_jsonl(str(self.evidence_path), record)

    def _record_matter(self, record: Dict[str, Any]) -> None:
        append_jsonl(str(self.matters_path), record)

    def _record_filing(self, record: Dict[str, Any]) -> None:
        append_jsonl(str(self.filings_path), record)

    def _read_records(self, path: Path) -> List[Dict[str, Any]]:
        return list(read_jsonl(str(path)))

    def list_cases(self) -> List[Dict[str, Any]]:
        cases = self._read_records(self.cases_path)
        if cases:
            merged: Dict[str, Dict[str, Any]] = {}
            for case in cases:
                cid = case.get("case_id") or "unassigned"
                current = merged.get(cid)
                if current is None or float(case.get("updated_at", 0)) >= float(current.get("updated_at", 0)):
                    merged[cid] = case
            return sorted(merged.values(), key=lambda item: float(item.get("updated_at", 0)), reverse=True)

        matters = self._read_records(self.matters_path)
        if matters:
            merged: Dict[str, Dict[str, Any]] = {}
            for matter in matters:
                cid = matter.get("case_id") or "unassigned"
                merged[cid] = {
                    "case_id": cid,
                    "title": matter.get("title") or cid.replace("-", " ").title(),
                    "status": matter.get("status", "active"),
                    "priority": DEFAULT_PRIORITY,
                    "created_at": matter.get("updated_at", time.time()),
                    "updated_at": matter.get("updated_at", time.time()),
                    "tags": intent_tags(" ".join([str(matter.get("practice_area", "")), str(matter.get("court_name", ""))])),
                }
            return sorted(merged.values(), key=lambda item: float(item.get("updated_at", 0)), reverse=True)

        grouped: Dict[str, Dict[str, Any]] = {}
        for doc in self._read_records(self.documents_path):
            cid = doc.get("case_id") or "unassigned"
            grouped.setdefault(
                cid,
                {
                    "case_id": cid,
                    "title": doc.get("case_title") or cid.replace("-", " ").title(),
                    "status": "active",
                    "priority": DEFAULT_PRIORITY,
                    "created_at": doc.get("timestamp", time.time()),
                    "updated_at": doc.get("timestamp", time.time()),
                    "tags": doc.get("tags", []),
                },
            )
        return sorted(grouped.values(), key=lambda item: float(item.get("updated_at", 0)), reverse=True)

    def list_matters(self) -> List[Dict[str, Any]]:
        matters = self._read_records(self.matters_path)
        if matters:
            merged: Dict[str, Dict[str, Any]] = {}
            for matter in matters:
                cid = matter.get("case_id") or "unassigned"
                current = merged.get(cid)
                if current is None or float(matter.get("updated_at", 0)) >= float(current.get("updated_at", 0)):
                    merged[cid] = matter
            return sorted(merged.values(), key=lambda item: float(item.get("updated_at", 0)), reverse=True)
        return [default_matter(case.get("case_id"), case.get("title")) for case in self.list_cases()]

    def get_matter(self, case_id: Optional[str]) -> Dict[str, Any]:
        case_id = str(case_id or "unassigned")
        for matter in reversed(self.list_matters()):
            if str(matter.get("case_id")) == case_id:
                return matter
        return default_matter(case_id)

    def upsert_matter(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        matter = default_matter(payload.get("case_id"), payload.get("title"))
        matter.update({k: v for k, v in payload.items() if v is not None})
        matter["updated_at"] = time.time()
        self._record_matter(matter)
        self._record_case(matter["case_id"], matter.get("title"), status=str(matter.get("status", "active")))
        return matter

    def list_documents(self, case_id: Optional[str] = None) -> List[Dict[str, Any]]:
        docs = self._read_records(self.documents_path)
        if case_id:
            docs = [doc for doc in docs if str(doc.get("case_id")) == str(case_id)]
        return docs

    def list_evidence(self, case_id: Optional[str] = None) -> List[Dict[str, Any]]:
        evidence = self._read_records(self.evidence_path)
        if case_id:
            evidence = [item for item in evidence if str(item.get("case_id")) == str(case_id)]
        return evidence

    def list_traces(self, case_id: Optional[str] = None) -> List[Dict[str, Any]]:
        traces = self._read_records(self.traces_path)
        if case_id:
            traces = [trace for trace in traces if str(trace.get("case_id")) == str(case_id)]
        return traces

    def legacy_memory_items(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for path, label in self._legacy_memory_paths():
            for rec in read_jsonl(str(path)):
                text = ""
                if label == "qa_override":
                    text = f"Q: {rec.get('q', '')} A: {rec.get('a', '')}"
                elif label == "fact":
                    text = f"{rec.get('fact', '')} {rec.get('notes', '')}"
                elif label == "block":
                    text = f"{rec.get('block', '')} {rec.get('reason', '')}"
                elif label == "pin":
                    text = f"{rec.get('pin_q', '')} {rec.get('pin_a', '')}"
                if not text.strip():
                    continue
                items.append(
                    {
                        "id": f"{label}:{rec.get('ts', _ts())}:{len(text)}",
                        "case_id": "legacy-memory",
                        "title": label.replace("_", " ").title(),
                        "source_type": label,
                        "source_name": path.name,
                        "text": text,
                        "timestamp": self._parse_ts(rec.get("ts")) or time.time(),
                        "priority": DEFAULT_PRIORITY,
                        "tags": intent_tags(text),
                        "metadata": rec,
                        "citation": f"[{path.stem}]",
                    }
                )
        return items

    def _parse_ts(self, value: Any) -> Optional[float]:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and value:
            try:
                return time.mktime(time.strptime(value, "%Y-%m-%dT%H:%M:%SZ"))
            except Exception:
                return None
        return None

    def _load_search_pool(self, case_id: Optional[str] = None) -> List[Dict[str, Any]]:
        pool = self.list_documents(case_id=case_id) + self.list_evidence(case_id=case_id) + self.list_traces(case_id=case_id)
        pool.extend(self._read_records(self.filings_path))
        pool.extend(self.legacy_memory_items())
        if case_id:
            pool = [item for item in pool if str(item.get("case_id")) in {str(case_id), "legacy-memory"}]
        return pool

    def score(self, query: str, item: Dict[str, Any]) -> MemoryHit:
        text = " ".join(
            [
                str(item.get("title", "")),
                str(item.get("text", "")),
                " ".join(item.get("tags", []) or []),
                json.dumps(item.get("metadata", {}), ensure_ascii=False),
            ]
        )
        sem = semantic_score(query, text)
        temp = temporal_score(float(item.get("timestamp") or time.time()))
        intent = intent_overlap(intent_tags(query), item.get("tags", []))
        priority = clamp01(float(item.get("priority", DEFAULT_PRIORITY)))
        final = final_weighted_score(sem, temp, intent, priority)
        return MemoryHit(item=item, semantic_score=sem, temporal_score=temp, intent_score=intent, priority_score=priority, final_score=final)

    def search(self, query: str, case_id: Optional[str] = None, top_k: int = 8) -> List[Dict[str, Any]]:
        pool = self._load_search_pool(case_id=case_id)
        hits = [self.score(query, item) for item in pool if item.get("text") or item.get("title")]
        hits.sort(key=lambda hit: hit.final_score, reverse=True)
        results = [hit.as_dict() for hit in hits[: max(1, top_k)]]
        self._cache = results
        append_jsonl(
            str(self.cache_path),
            {"timestamp": time.time(), "query": query, "case_id": case_id, "items": results[:5]},
        )
        return results

    def matter_profile(self, case_id: Optional[str] = None) -> Dict[str, Any]:
        matter = self.get_matter(case_id)
        return {
            "matter": matter,
            "court_profile": get_court_profile(matter.get("court_profile_id")),
            "court_profiles": list_court_profiles(),
            "templates": list_filing_templates(),
        }

    def observe_and_recall(self, user_input: str, case_id: Optional[str] = None, top_k: int = 5, ingest: bool = False) -> tuple[str, List[Dict[str, Any]]]:
        if ingest:
            self.ingest_text(user_input, case_id=case_id, case_title=case_id or "unassigned", source_type="observation")
        items = self.search(user_input, case_id=case_id, top_k=top_k)
        if not items:
            return "", []
        lines = [
            "[ARE-GLASSES-RECALL]",
            "instruction: Treat these as memory leads, not automatic truth. Use only relevant items.",
        ]
        for item in items:
            lines.append(
                "---\n"
                f"source: {item.get('source_name', item.get('source_type', 'memory'))}\n"
                f"score: {item.get('final_score', 0)}\n"
                f"text: {self.cap_text(str(item.get('text', '')), 700)}"
            )
        lines.append("[/ARE-GLASSES-RECALL]")
        return "\n".join(lines), items

    def stabilize_vision(self, user_input: str, case_id: Optional[str] = None, top_k: int = 5, ingest: bool = False) -> Dict[str, Any]:
        if ingest:
            self.ingest_text(user_input, case_id=case_id, case_title=case_id or "unassigned", source_type="observation")
        query_tokens = set(tokenize(user_input))
        recent_tokens = set(tokenize(" ".join(item["text"] for item in self._gyro_recent[-10:])))
        velocity = round(min(1.0, len(query_tokens - recent_tokens) / max(1, len(query_tokens))), 3) if query_tokens else 0.0
        visor, items = self.observe_and_recall(user_input, case_id=case_id, top_k=top_k, ingest=False)
        stabilized: List[Dict[str, Any]] = []
        seen = set()
        for idx, item in enumerate(items):
            text = self.cap_text(str(item.get("text", "")), 600)
            key = text.lower()[:220]
            if not text or key in seen:
                continue
            seen.add(key)
            score = float(item.get("final_score", 0.0))
            if idx == 0:
                score *= 1.1
            stabilized.append(
                {
                    "axis": "historical" if item.get("source_type") != "recent" else "recent",
                    "source": item.get("source_name") or item.get("source_type") or "unknown",
                    "text": text,
                    "gyro_score": round(score, 3),
                }
            )
        self._gyro_recent.append({"text": user_input, "source": "current"})
        self._gyro_recent = self._gyro_recent[-24:]
        lines = [
            "[GYRO-STABILIZED-RECALL]",
            f"semantic_velocity: {velocity}",
            "instruction: Use this visor to maintain topical focus. Treat memory as evidence leads, not automatic truth.",
        ]
        for chunk in stabilized[:top_k]:
            lines.append(
                "---\n"
                f"axis: {chunk['axis']}\n"
                f"source: {chunk['source']}\n"
                f"gyro_score: {chunk['gyro_score']}\n"
                f"text: {chunk['text']}"
            )
        lines.append("[/GYRO-STABILIZED-RECALL]")
        return {
            "visor": "\n".join(lines) if stabilized else visor,
            "items": stabilized[:top_k] if stabilized else items,
            "semantic_velocity": velocity,
            "timing_ms": 0.0,
        }

    def generate_gyro_prompt(
        self,
        user_input: str,
        system_instruction: str = "You are a helpful assistant.",
        case_id: Optional[str] = None,
        top_k: int = 5,
        ingest: bool = False,
    ) -> Dict[str, Any]:
        result = self.stabilize_vision(user_input, case_id=case_id, top_k=top_k, ingest=ingest)
        prompt = "\n\n".join(
            block
            for block in [
                f"SYSTEM: {system_instruction}",
                result.get("visor", ""),
                f"USER: {user_input}",
                "ASSISTANT:",
            ]
            if block
        )
        result["prompt"] = prompt
        return result

    def analyze_matter(self, query: str = "", case_id: Optional[str] = None, top_k: int = 8) -> Dict[str, Any]:
        records = self.search(query or "legal intelligence", case_id=case_id, top_k=top_k)
        timeline = self.timeline(case_id=case_id, limit=50)
        matter = self.get_matter(case_id)
        scenarios = rank_scenarios(records, query=query)
        anomalies = detect_anomalies(records, timeline)
        exhibit_index = build_exhibit_index(records, limit=12)
        billing = estimate_billing(
            records,
            increment_minutes=int(matter.get("billing_increment_minutes", 15)),
            hourly_rate=float(matter.get("billing_rate", 0.0)),
        )
        filing_suggestions = [
            {
                "template_id": "motion_to_compel",
                "title": "Motion to Compel + MPA",
                "reason": "Discovery record shows missing or weak responses.",
            },
            {
                "template_id": "case_theory_memo",
                "title": "Case Theory Memo",
                "reason": "Use this to pressure-test the strongest and adverse scenarios.",
            },
            {
                "template_id": "timeline_summary",
                "title": "Timeline Summary",
                "reason": "A chronology will help the lawyer see the most important facts at a glance.",
            },
        ]
        if any(word in query.lower() for word in ["dismiss", "jurisdiction", "standing"]):
            filing_suggestions.insert(0, {"template_id": "motion_to_dismiss", "title": "Motion to Dismiss", "reason": "Threshold defect question was detected in the query."})
        if any(word in query.lower() for word in ["summary", "judgment", "undisputed"]):
            filing_suggestions.insert(0, {"template_id": "summary_judgment", "title": "Motion for Summary Judgment", "reason": "Query suggests undisputed-facts posture."})
        return {
            "matter": matter,
            "court_profile": get_court_profile(matter.get("court_profile_id")),
            "records": records,
            "timeline": timeline,
            "scenarios": scenarios,
            "anomalies": anomalies,
            "exhibit_index": exhibit_index,
            "billing": billing,
            "filing_suggestions": filing_suggestions[:5],
        }

    def build_packet(self, template_id: str, case_id: Optional[str] = None, query: str = "") -> Dict[str, Any]:
        matter = self.get_matter(case_id)
        records = self.search(query or matter.get("title", "legal intelligence"), case_id=case_id, top_k=12)
        timeline = self.timeline(case_id=case_id, limit=80)
        packet = build_filing_packet(template_id=template_id, matter=matter, records=records, timeline=timeline, query=query)
        filing_record = {
            "timestamp": time.time(),
            "case_id": matter.get("case_id", "unassigned"),
            "template_id": template_id,
            "title": packet["template"]["title"],
            "summary": packet["scenarios"][0]["summary"] if packet["scenarios"] else "",
            "metadata": {"billing": packet["checklist"], "court_profile": packet["court_profile"]},
        }
        self._record_filing(filing_record)
        self._record_trace(
            {
                "timestamp": time.time(),
                "case_id": matter.get("case_id", "unassigned"),
                "event_type": "draft",
                "title": packet["template"]["title"],
                "summary": packet["scenarios"][0]["summary"] if packet["scenarios"] else "",
                "metadata": {"template_id": template_id},
            }
        )
        return packet

    def cache(self) -> List[Dict[str, Any]]:
        return self._cache

    def prompt_prefix(self, max_chars: int = 1400, case_id: Optional[str] = None) -> str:
        items = self._cache or self.search("legal intelligence", case_id=case_id, top_k=4)
        lines: List[str] = []
        total = 0
        for item in items:
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            line = f"[score={item.get('final_score', 0):.3f} source={item.get('source_type', 'unknown')} case={item.get('case_id', 'unassigned')}]\n{text}"
            if total + len(line) > max_chars:
                break
            lines.append(line)
            total += len(line)
        return "\n---\n".join(lines)

    def gyro_debug(self, case_id: Optional[str] = None) -> Dict[str, Any]:
        return {
            "weights": {"semantic": SEMANTIC_WEIGHT, "temporal": TEMPORAL_WEIGHT, "intent": INTENT_WEIGHT, "priority": PRIORITY_WEIGHT},
            "cache_size": len(self._cache),
            "dynamic_memory": {
                "mode": "hot_working_memory_with_dynamic_echo_themes",
                "recent": self._gyro_recent[-8:],
            },
            "items": self.cache() if not case_id else [item for item in self.cache() if str(item.get("case_id")) == str(case_id)],
        }

    def timeline(self, case_id: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for doc in self._load_search_pool(case_id=case_id):
            items.append(
                {
                    "timestamp": doc.get("timestamp", time.time()),
                    "case_id": doc.get("case_id", "unassigned"),
                    "title": doc.get("title") or doc.get("source_name") or "Untitled",
                    "event_type": doc.get("source_type", "document"),
                    "summary": str(doc.get("text", ""))[:240],
                    "citation": doc.get("citation") or f"[{doc.get('source_name', 'source')}]",
                    "metadata": doc.get("metadata", {}),
                }
            )
        items.sort(key=lambda item: float(item.get("timestamp", 0)), reverse=True)
        return items[: max(1, limit)]

    def trace_report(self, trace_id: str) -> str:
        trace = self.read_trace(trace_id)
        if not trace:
            return ""
        lines = [
            f"# Trace {trace_id}",
            "",
            f"- Timestamp: {trace.get('timestamp', '')}",
            f"- Case: {trace.get('case_id', '')}",
            f"- Event: {trace.get('event_type', '')}",
            f"- Title: {trace.get('title', '')}",
            "",
            "## Summary",
            trace.get("summary", ""),
        ]
        return "\n".join(lines)

    def memory_status(self) -> Dict[str, Any]:
        docs = self._read_records(self.documents_path)
        cases = self.list_cases()
        matters = self.list_matters()
        evidence = self.list_evidence()
        filings = self._read_records(self.filings_path)
        traces = self.list_traces()
        legacy = self.legacy_memory_items()
        return {
            "documents": len(docs),
            "cases": len(cases),
            "matters": len(matters),
            "evidence": len(evidence),
            "filings": len(filings),
            "traces": len(traces),
            "legacy_items": len(legacy),
            "last_cache_size": len(self._cache),
            "storage": {"memory_dir": str(self.memory_dir), "vault_dir": str(self.vault_dir), "knowledge_dir": str(self.knowledge_dir)},
        }

    def cap_text(self, text: str, limit: int = 900) -> str:
        clean = " ".join(str(text or "").split())
        if len(clean) <= limit:
            return clean
        return clean[:limit].rsplit(" ", 1)[0] + "..."

    def ingest_text(
        self,
        text: str,
        *,
        case_id: Optional[str] = None,
        case_title: Optional[str] = None,
        source_type: str = "upload",
        file_name: Optional[str] = None,
        mime_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        clean = re.sub(r"\s+", " ", (text or "").strip())
        if not clean:
            return {"chunks": 0, "case_id": case_id or "unassigned", "items": []}

        case_id = case_id or slugify(case_title or file_name or "unassigned")
        case_title = case_title or (Path(file_name).stem if file_name else None) or case_id.replace("-", " ").title()
        self._record_case(case_id, case_title)

        chunks = chunk_text(clean)
        now = time.time()
        items = []
        for index, chunk in enumerate(chunks):
            record = {
                "id": f"{case_id}:{slugify(file_name or case_title)}:{index}",
                "case_id": case_id,
                "case_title": case_title,
                "title": case_title,
                "source_type": source_type,
                "source_name": file_name or case_title or case_id,
                "mime_type": mime_type,
                "chunk_index": index,
                "text": chunk,
                "timestamp": now,
                "priority": DEFAULT_PRIORITY,
                "tags": intent_tags(f"{case_title} {chunk}"),
                "citation": f"[{file_name or case_title} #{index + 1}]",
                "metadata": metadata or {},
            }
            self._record_document(record)
            self._record_evidence(record)
            items.append(record)

        self._record_trace(
            {
                "timestamp": now,
                "case_id": case_id,
                "event_type": "ingest",
                "title": case_title,
                "summary": f"Ingested {len(items)} chunk(s) from {file_name or case_title}",
                "metadata": metadata or {},
            }
        )
        return {"chunks": len(items), "case_id": case_id, "case_title": case_title, "items": items}

    def ingest_blob(
        self,
        *,
        content_b64: Optional[str],
        text: Optional[str] = None,
        file_name: Optional[str] = None,
        mime_type: Optional[str] = None,
        case_id: Optional[str] = None,
        case_title: Optional[str] = None,
        source_type: str = "upload",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        if text and text.strip():
            return self.ingest_text(text, case_id=case_id, case_title=case_title, source_type=source_type, file_name=file_name, mime_type=mime_type, metadata=metadata)

        raw = b""
        if content_b64:
            raw = base64.b64decode(content_b64)

        extracted = self.extract_text_from_bytes(raw, file_name=file_name, mime_type=mime_type)
        if not extracted.strip():
            extracted = f"[binary upload preserved: {file_name or 'unnamed'}]"
        upload_path = self.save_upload(raw, file_name=file_name, mime_type=mime_type)
        payload = dict(metadata or {})
        payload["upload_path"] = str(upload_path)
        return self.ingest_text(
            extracted,
            case_id=case_id,
            case_title=case_title,
            source_type=source_type,
            file_name=file_name or upload_path.name,
            mime_type=mime_type,
            metadata=payload,
        )

    def save_upload(self, raw: bytes, *, file_name: Optional[str], mime_type: Optional[str]) -> Path:
        safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", file_name or f"upload_{int(time.time())}")
        target = self.upload_dir / safe_name
        target.write_bytes(raw or b"")
        return target

    def extract_text_from_bytes(self, raw: bytes, *, file_name: Optional[str], mime_type: Optional[str]) -> str:
        suffix = Path(file_name or "").suffix.lower()
        mime = (mime_type or "").lower()
        if not raw:
            return ""

        if suffix in {".txt", ".md", ".csv", ".json", ".log", ".xml", ".html", ".htm", ".yml", ".yaml", ".py"} or mime.startswith("text/"):
            text = raw.decode("utf-8", errors="ignore")
            if suffix in {".html", ".htm"} or mime == "text/html":
                text = strip_html(text)
            return re.sub(r"\s+", " ", text).strip()

        if suffix == ".docx" or mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            try:
                if docx is not None:
                    document = docx.Document(io.BytesIO(raw))
                    return re.sub(r"\s+", " ", "\n".join(paragraph.text for paragraph in document.paragraphs)).strip()
            except Exception:
                pass

        if suffix == ".pdf" or mime == "application/pdf":
            try:
                if PyPDF2 is None:
                    return ""
                reader = PyPDF2.PdfReader(io.BytesIO(raw))
                text = "\n".join(page.extract_text() or "" for page in reader.pages)
                return re.sub(r"\s+", " ", text).strip()
            except Exception:
                return ""

        if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff"} or mime.startswith("image/"):
            try:
                if pytesseract is not None and Image is not None:
                    image = Image.open(io.BytesIO(raw))
                    text = pytesseract.image_to_string(image)
                    return re.sub(r"\s+", " ", text).strip()
            except Exception:
                return ""

        try:
            return raw.decode("utf-8", errors="ignore").strip()
        except Exception:
            return ""

    def load_corpus_folder(self, path: str, *, case_id: Optional[str] = None) -> Dict[str, Any]:
        folder = Path(path)
        if not folder.exists():
            return {"loaded_chunks": 0, "items": [], "case_id": case_id or "unassigned"}

        loaded = 0
        items: List[Dict[str, Any]] = []
        for candidate in folder.rglob("*"):
            if not candidate.is_file():
                continue
            suffix = candidate.suffix.lower()
            if suffix == ".zip" and legacy_parser is not None:
                extracted = legacy_parser.iter_files_in_zip(candidate)
                for nested in extracted:
                    text = ""
                    try:
                        text = legacy_parser.extract_text(nested)
                    except Exception:
                        text = ""
                    if not text.strip():
                        continue
                    result = self.ingest_text(
                        text,
                        case_id=case_id,
                        case_title=nested.stem,
                        source_type="corpus",
                        file_name=nested.name,
                        mime_type="text/plain",
                        metadata={"path": str(nested), "archive": str(candidate)},
                    )
                    loaded += int(result.get("chunks", 0))
                    items.extend(result.get("items", []))
                continue
            if suffix not in {".txt", ".md", ".json", ".html", ".htm", ".csv", ".log", ".docx", ".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
                continue
            try:
                if legacy_parser is not None:
                    text = legacy_parser.extract_text(candidate)
                else:
                    text = candidate.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            result = self.ingest_text(
                text,
                case_id=case_id,
                case_title=candidate.stem,
                source_type="corpus",
                file_name=candidate.name,
                mime_type="text/plain",
                metadata={"path": str(candidate)},
            )
            loaded += int(result.get("chunks", 0))
            items.extend(result.get("items", []))
        return {"loaded_chunks": loaded, "items": items, "case_id": case_id or "unassigned"}

    def ocr_image(self, raw: bytes, *, file_name: Optional[str] = None, mime_type: Optional[str] = None) -> Dict[str, Any]:
        try:
            if pytesseract is not None and Image is not None:
                image = Image.open(io.BytesIO(raw))
                text = pytesseract.image_to_string(image)
                return {"ok": True, "text": re.sub(r"\s+", " ", text).strip(), "engine": "pytesseract"}
        except Exception as exc:
            return {"ok": False, "text": "", "engine": "unavailable", "message": f"OCR unavailable for {file_name or 'image'}: {exc}"}
        return {"ok": False, "text": "", "engine": "unavailable", "message": f"OCR unavailable for {file_name or 'image'}"}

    def decode_blob(self, content_b64: Optional[str]) -> bytes:
        return base64.b64decode(content_b64) if content_b64 else b""

    def read_trace(self, trace_id: str) -> Dict[str, Any]:
        for row in reversed(self.list_traces()):
            if str(row.get("trace_id")) == str(trace_id):
                return row
        return {}

    def append_trace(self, payload: Dict[str, Any]) -> str:
        trace_id = payload.get("trace_id") or slugify(f"{payload.get('case_id', 'trace')}-{int(time.time())}")
        payload = dict(payload)
        payload["trace_id"] = trace_id
        append_jsonl(str(self.traces_path), payload)
        return trace_id
