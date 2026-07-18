from __future__ import annotations

import base64
import importlib.util
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from .models import AnalysisRequest, AuthorityStampRequest, BillingRequest, ChatRequest, CourtListenerCitationRequest, CourtListenerIngestRequest, CourtListenerLookupRequest, CourtListenerSearchRequest, CourtProfileRequest, CourtRulesLoadRequest, DocketImportRequest, DraftRequest, EdgarCompanyRequest, EdgarIngestRequest, EdgarSearchRequest, ExportRequest, FirmProfileRequest, GyroRequest, IngestRequest, LoadCorpusRequest, MatterRequest, OCRRequest, PromptPrefixRequest, SearchRequest, StaffDirectoryRequest, SuggestRequest, TimelineRequest
from .services.california_regulations import CaliforniaRegulationsClient, CaliforniaRegulationsError
from .services.config import external_source_status, load_local_env
from .services.continuity import build_staff_continuity_status
from .services.courtlistener import CourtListenerClient
from .services.llm import LocalModelClient, build_chat_mode_context, build_legal_system_prompt, normalize_chat_mode
from .services.legal_intel import court_profile_report as build_court_profile_report, packet_to_docx_bytes, packet_to_markdown, packet_to_pdf_bytes, scan_packet
from .services.public_web import PublicWebSearchClient, PublicWebSearchError
from .services.workspace import FIRM_ROLE_PERMISSIONS, WorkspaceStore
from demo_seed import seed_harbor_point_demo
from license_manager import activate_license, ensure_license, license_summary, verify_license
from veritas_claire_runtime import VeritasClaireRuntime
from veritas_court_listener import VeritasCourtListener
from veritas_edgar import VeritasEdgar
from veritas_source_trace import build_source_trace, write_source_trace

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
STATIC_DIR = WEB_DIR / "static"
INDEX_FILE = WEB_DIR / "index.html"

load_local_env(ROOT)

app = FastAPI(title="CLAIRE // VERITAS LEGAL", version="1.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

STORE = WorkspaceStore(ROOT)
LLM = LocalModelClient()
COURTLISTENER = CourtListenerClient()
CALIFORNIA_REGULATIONS = CaliforniaRegulationsClient()
PUBLIC_WEB = PublicWebSearchClient()
VERITAS_RUNTIME = VeritasClaireRuntime(ROOT)
VERITAS_COURT_LISTENER = VeritasCourtListener(ROOT, COURTLISTENER)
VERITAS_EDGAR = VeritasEdgar(ROOT)
COURTLISTENER_LOG = logging.getLogger("veritas.courtlistener")
PUBLIC_RESEARCH_LOG = logging.getLogger("veritas.public_research")
CREATOR_PASSPHRASE = os.getenv("VERITAS_CREATOR_PASSPHRASE", "").strip()
CREATOR_SESSION_UNLOCKED = False
CREATOR_GREETING = (
    "Creator Mode acknowledged. Welcome back, Lucius Prime. "
    "Creator continuity is now active, Cody remains on systems watch, "
    "and Claire stays grounded to the active matter."
)


def _firm_tier_continuity_enabled() -> bool:
    return str(os.getenv("VERITAS_FIRM_TIER_CONTINUITY", "")).strip().lower() in {"1", "true", "yes", "on"}


def _case_context(case_id: Optional[str]) -> Dict[str, Any]:
    matter_bundle = STORE.matter_profile(case_id)
    return {
        "case_id": case_id or "unassigned",
        "cases": STORE.list_cases(),
        "matter": matter_bundle.get("matter", {}),
        "court_profile": matter_bundle.get("court_profile", {}),
        "documents": STORE.list_documents(case_id=case_id),
        "evidence": STORE.list_evidence(case_id=case_id),
        "timeline": STORE.timeline(case_id=case_id, limit=40),
    }


def _build_context(query: str, case_id: Optional[str], top_k: int) -> Dict[str, Any]:
    hits = STORE.search(query, case_id=case_id, top_k=top_k)
    context_lines = []
    for index, item in enumerate(hits, 1):
        source = item.get("citation") or item.get("source_name") or item.get("id") or "source"
        context_lines.append(
            f"[{index}] {source} | score={item.get('final_score', 0):.3f} | case={item.get('case_id', 'unassigned')}\n{item.get('text', '')}"
        )
    return {"hits": hits, "context_text": "\n\n".join(context_lines), "prefix": STORE.prompt_prefix(case_id=case_id)}


def _grounded_fallback_reply(query: str, bundle: Dict[str, Any], case_id: Optional[str] = None) -> str:
    hits = []
    for item in list(bundle.get("hits") or []):
        if item.get("event_type") == "chat":
            continue
        text = str(item.get("text") or "").strip()
        if not text or text.startswith("The grounded record has matching material"):
            continue
        hits.append(item)
    if not hits and case_id:
        query_terms = {part for part in query.lower().split() if len(part) > 3}
        for item in STORE.list_evidence(case_id=case_id):
            text = str(item.get("text") or "").strip()
            if not text:
                continue
            text_lower = text.lower()
            if query_terms and not any(term in text_lower for term in query_terms):
                continue
            hits.append(item)
    if not hits:
        return (
            "No grounded matter records matched the request. Add or ingest evidence, then rerun the query so the answer can cite source material."
        )
    lines = [
        "The grounded record has matching material, but the local model returned no draft. Based on the indexed evidence:",
    ]
    for item in hits[:4]:
        citation = item.get("citation") or item.get("source_name") or item.get("trace_id") or "source"
        text = str(item.get("text") or "").strip()
        if not text:
            continue
        lines.append(f"- {text[:360]} [{citation}]")
    lines.append("Treat this as evidence orientation, not legal advice. Attorney review is still required before any legal action.")
    return "\n".join(lines)


def _local_evidence_support_intent(query: str) -> bool:
    text = " ".join((query or "").lower().split())
    if not text:
        return False
    support_markers = (
        "what evidence supports",
        "which evidence supports",
        "what records support",
        "which records support",
        "show supporting evidence",
        "source trace",
        "cite the evidence",
    )
    return any(marker in text for marker in support_markers)


def _fast_matter_evidence_reply(query: str, bundle: Dict[str, Any], case_id: Optional[str]) -> str:
    hits = [item for item in (bundle.get("hits") or []) if str(item.get("case_id") or "") == str(case_id or item.get("case_id") or "")]
    if not hits:
        return _grounded_fallback_reply(query, bundle, case_id=case_id)
    lines = [
        "I found supporting material in the active matter record. Attorney review is required before relying on it:",
    ]
    for item in hits[:5]:
        citation = item.get("citation") or item.get("source_name") or item.get("id") or "source"
        title = item.get("source_name") or item.get("title") or citation
        text = str(item.get("text") or item.get("summary") or "").strip()
        if not text:
            continue
        lines.append(f"- {title}: {text[:360]} [{citation}]")
    lines.append("This is an evidence-grounded orientation, not legal advice or a filing-ready conclusion.")
    return "\n".join(lines)


def _legal_research_intent(query: str) -> Dict[str, Any]:
    text = " ".join((query or "").split()).lower()
    if not text:
        return {"matches": False, "reason": "empty"}
    legal_markers = (
        "court",
        "case",
        "docket",
        "opinion",
        "order",
        "motion",
        "brief",
        "complaint",
        "discovery",
        "summary judgment",
        "judgment",
        "appeal",
        "citation",
        "authority",
        "precedent",
        "filing",
        "hearing",
        "law",
        "statute",
        "judge",
        "judges",
        "plaintiff",
        "defendant",
        "appellant",
        "appellee",
    )
    if any(marker in text for marker in legal_markers):
        return {"matches": True, "reason": "legal_marker"}
    if re.search(r"(?:^|\s)(?:v\.?|vs\.?|versus)(?:\s|$)", text):
        return {"matches": True, "reason": "case_caption"}
    if re.search(r"\b\d+\s+(?:u\.s\.|f\.\s?\d+d|f\.\s?supp\.?\s?\d*d?|s\.\s?ct\.)\s+\d+\b", text):
        return {"matches": True, "reason": "reporter_citation"}
    if re.search(r"\b(?:no\.|case\s+no\.|docket\s+no\.)\s*[\w:.-]+", text):
        return {"matches": True, "reason": "docket_reference"}
    if re.search(r"\bccr\b|c\.?\s*c\.?\s*r\.?|california\s+code\s+of\s+regulations|§\s*\d{3,5}", text):
        return {"matches": True, "reason": "regulation_reference"}
    return {"matches": False, "reason": "no_legal_research_signal"}


def _public_regulatory_context(query: str) -> Dict[str, Any]:
    if not re.search(r"\bccr\b|c\.?\s*c\.?\s*r\.?|california\s+code\s+of\s+regulations", query or "", flags=re.I):
        return {"used": False, "reason": "no_regulatory_signal", "results": [], "count": 0}
    PUBLIC_RESEARCH_LOG.warning("calregs.invoke query=%r", query)
    try:
        result = CALIFORNIA_REGULATIONS.lookup(query)
    except CaliforniaRegulationsError as exc:
        PUBLIC_RESEARCH_LOG.warning("calregs.error query=%r error=%s", query, exc)
        return {"used": False, "reason": "calregs_error", "error": str(exc), "results": [], "count": 0}
    PUBLIC_RESEARCH_LOG.warning(
        "calregs.response query=%r used=%s reason=%s count=%s",
        query,
        result.get("used"),
        result.get("reason"),
        result.get("count"),
    )
    return result


def _should_use_public_web(query: str, research_intent: Dict[str, Any]) -> bool:
    text = " ".join(str(query or "").lower().split())
    if not text:
        return False
    evidence_only_markers = (
        "in the evidence",
        "in evidence",
        "uploaded evidence",
        "local evidence",
        "matter record",
        "case record",
        "active matter",
        "this matter",
        "my evidence",
        "our evidence",
        "timeline",
        "exhibit",
    )
    if any(marker in text for marker in evidence_only_markers):
        return False
    explicit = ("web", "online", "internet", "look up", "lookup", "search", "find", "current", "latest")
    if any(marker in text for marker in explicit):
        return True
    if research_intent.get("matches"):
        return True
    if re.search(r"\bccr\b|c\.?\s*c\.?\s*r\.?|§\s*\d{3,5}|code\s+section|regulation|statute|agency|rule", text):
        return True
    return True


def _public_web_context(query: str, research_intent: Dict[str, Any]) -> Dict[str, Any]:
    if not _should_use_public_web(query, research_intent):
        return {"used": False, "reason": "no_public_web_signal", "results": [], "count": 0}
    PUBLIC_RESEARCH_LOG.warning("public_web.invoke query=%r", query)
    try:
        result = PUBLIC_WEB.search(query, max_results=4)
    except PublicWebSearchError as exc:
        PUBLIC_RESEARCH_LOG.warning("public_web.error query=%r error=%s", query, exc)
        return {"used": False, "reason": "public_web_error", "error": str(exc), "results": [], "count": 0}
    PUBLIC_RESEARCH_LOG.warning(
        "public_web.response query=%r used=%s reason=%s count=%s",
        query,
        result.get("used"),
        result.get("reason"),
        result.get("count"),
    )
    return result


def _fast_regulatory_reply(query: str, regulatory_context: Dict[str, Any]) -> str:
    items = regulatory_context.get("results") or []
    if not items:
        if regulatory_context.get("reason") == "calregs_error":
            return "I tried to search public California regulation sources, but the regulation lookup is temporarily unavailable. Verify directly against the official California Code of Regulations."
        return "I searched public California regulation sources but did not find a matching regulation."
    item = items[0]
    lines = [
        "I searched public California regulation sources before generating this response.",
        f"Matched source: {item.get('citation') or item.get('title')}.",
    ]
    if item.get("currentness"):
        lines.append(f"Currentness shown by source: {item.get('currentness')}.")
    lines.append(str(item.get("text") or item.get("snippet") or "").strip())
    if item.get("source_url"):
        lines.append(f"Public source: {item.get('source_url')}")
    if item.get("official_index_url"):
        lines.append(f"Official CCR index for verification: {item.get('official_index_url')}")
    lines.append("This is source-linked legal research support, not legal advice. Verify currentness before relying on it.")
    return "\n\n".join(line for line in lines if line)


def _fast_public_web_reply(query: str, public_web_context: Dict[str, Any]) -> str:
    items = public_web_context.get("results") or []
    if not items:
        if public_web_context.get("reason") == "public_web_error":
            return "I tried to search the public web, but the web research source is temporarily unavailable. Try again shortly or provide a source URL to inspect."
        return "I searched the public web but did not find matching public results."
    lines = ["I searched the public web before generating this response."]
    for index, item in enumerate(items[:4], 1):
        title = item.get("title") or "Public web result"
        snippet = item.get("snippet") or ""
        url = item.get("source_url") or ""
        lines.append(f"{index}. {title}\n{snippet}\nSource: {url}".strip())
    lines.append("Use these as source leads. Verify primary and official sources before legal reliance.")
    return "\n\n".join(lines)


def _should_use_recognition_rail(query: str, mode: Optional[str], case_id: Optional[str]) -> bool:
    if normalize_chat_mode(mode) != "legal":
        return False
    text = " ".join((query or "").split()).lower()
    if not text:
        return False
    intent = _legal_research_intent(query)
    return bool(intent["matches"])


def _build_recognition_rail_prefix(
    query: str,
    *,
    search_type: str = "o",
    page_size: int = 3,
    semantic: bool = False,
    timeout: int = 20,
) -> Dict[str, Any]:
    COURTLISTENER_LOG.warning(
        "courtlistener.invoke query=%r search_type=%s page_size=%s semantic=%s",
        query,
        search_type,
        page_size,
        semantic,
    )
    try:
        result = COURTLISTENER.search(
            query,
            search_type=search_type,
            page_size=page_size,
            semantic=semantic,
            timeout=timeout,
        )
    except requests.HTTPError as exc:  # type: ignore[name-defined]
        status = exc.response.status_code if exc.response is not None else 502
        COURTLISTENER_LOG.warning("courtlistener.http_error query=%r status=%s error=%s", query, status, exc)
        return {
            "used": False,
            "reason": f"courtlistener_http_{status}",
            "error": str(exc),
            "prefix": "",
            "results": [],
            "count": 0,
            "semantic": semantic,
            "page_size": page_size,
        }
    except Exception as exc:
        COURTLISTENER_LOG.warning("courtlistener.error query=%r error=%s", query, exc)
        return {
            "used": False,
            "reason": "courtlistener_error",
            "error": str(exc),
            "prefix": "",
            "results": [],
            "count": 0,
            "semantic": semantic,
            "page_size": page_size,
        }
    prefix_lines = [
        "[ARE-COURTLISTENER-PREFETCH]",
        f"query: {query}",
        f"search_type: {search_type or 'r'}",
    ]
    items = result.get("results") or []
    COURTLISTENER_LOG.warning(
        "courtlistener.response query=%r count=%s returned=%s warnings=%s",
        query,
        result.get("count", len(items)),
        len(items),
        result.get("warnings") or [],
    )
    for item in items[: max(1, min(int(page_size or 3), 10))]:
        prefix_lines.append(
            "---\n"
            f"title: {item.get('title') or 'CourtListener Result'}\n"
            f"court: {item.get('court') or 'Unknown'}\n"
            f"date_filed: {item.get('date_filed') or 'Unknown'}\n"
            f"docket_number: {item.get('docket_number') or 'Unknown'}\n"
            f"source_url: {item.get('source_url') or 'n/a'}\n"
            f"snippet: {item.get('snippet') or ''}"
        )
    prefix_lines.append("[/ARE-COURTLISTENER-PREFETCH]")
    return {
        "used": bool(items),
        "reason": "courtlistener_prefetch",
        "query": query,
        "count": result.get("count", len(items)),
        "results": items,
        "prefix": "\n".join(prefix_lines),
        "semantic": semantic,
        "page_size": page_size,
    }


def _recognition_rail_context(query: str, case_id: Optional[str], mode: Optional[str], top_k: int) -> Dict[str, Any]:
    intent = _legal_research_intent(query)
    COURTLISTENER_LOG.warning(
        "courtlistener.intent query=%r mode=%s case_id=%s matches=%s reason=%s",
        query,
        normalize_chat_mode(mode),
        case_id,
        intent["matches"],
        intent["reason"],
    )
    if not _should_use_recognition_rail(query, mode, case_id):
        COURTLISTENER_LOG.warning("courtlistener.skipped query=%r reason=classifier_%s", query, intent["reason"])
        return {
            "used": False,
            "reason": "skipped",
            "query": query,
            "intent": intent,
            "count": 0,
            "results": [],
            "prefix": "",
            "semantic": False,
            "page_size": 0,
        }
    payload = _build_recognition_rail_prefix(query, page_size=max(1, min(int(top_k or 3), 3)), semantic=False)
    payload["intent"] = intent
    return payload


def _fast_legal_research_reply(query: str, bundle: Dict[str, Any], recognition_rail: Dict[str, Any]) -> str:
    rail_items = recognition_rail.get("results") or []
    lines = ["I searched CourtListener before generating this response."]
    if rail_items:
        rail_labels = []
        for item in rail_items[:3]:
            label = item.get("title") or "CourtListener result"
            docket = item.get("docket_number") or "docket n/a"
            court = item.get("court") or "court n/a"
            filed = item.get("date_filed") or "date n/a"
            url = item.get("source_url") or "source n/a"
            rail_labels.append(f"{label} ({court}, {docket}, filed {filed}) {url}")
        lines.append("CourtListener results: " + "; ".join(rail_labels))
    else:
        lines.append("CourtListener results: none returned.")
    lines.append("CourtListener and RECAP can be partial or stale; verify against the official docket when completeness matters.")
    return " ".join(lines)


def _veritas_thinking_enabled(query: str, mode: Optional[str]) -> bool:
    if normalize_chat_mode(mode) != "legal":
        return False
    lowered = str(query or "").lower()
    thinking_markers = (
        "analyze",
        "analysis",
        "analiza",
        "analizar",
        "análisis",
        "argument",
        "argumento",
        "argue",
        "brief",
        "contradiction",
        "contradictions",
        "contradicción",
        "contradicciones",
        "compare",
        "comparar",
        "conflict",
        "conflicto",
        "disputed",
        "disputa",
        "evidence synthesis",
        "síntesis",
        "issue",
        "cuestión",
        "problema legal",
        "memo",
        "motion",
        "synthesize",
        "synthesis",
        "timeline",
        "cronología",
        "chronology",
        "theory",
        "teoría",
        "weakness",
        "debilidad",
        "risk",
        "riesgo",
    )
    non_thinking_markers = (
        "summarize",
        "summary",
        "what is",
        "what does",
        "who is",
        "where is",
        "find",
        "show me",
        "retrieve",
        "quote",
        "citation",
        "source",
    )
    if any(marker in lowered for marker in thinking_markers):
        return True
    if any(marker in lowered for marker in non_thinking_markers):
        return False
    return False


def _module_available(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _ocr_available() -> bool:
    return _module_available("pytesseract") and _module_available("PIL")


def _memory_activity(status: Dict[str, Any]) -> Dict[str, Any]:
    documents = int(status.get("documents", 0) or 0)
    evidence = int(status.get("evidence", 0) or 0)
    traces = int(status.get("traces", 0) or 0)
    return {
        "indexed": (documents + evidence) > 0,
        "documents": documents,
        "evidence": evidence,
        "traces": traces,
        "workflow": {
            "ingest": documents > 0,
            "index": evidence > 0,
            "query": traces > 0,
            "trace": traces > 0,
            "timeline": traces > 0 or evidence > 0,
        },
    }


def _ingest_payload(payload: IngestRequest) -> Dict[str, Any]:
    return STORE.ingest_blob(
        content_b64=payload.content_b64,
        text=payload.text,
        file_name=payload.file_name,
        mime_type=payload.mime_type,
        case_id=payload.case_id,
        case_title=payload.case_title,
        source_type=payload.source_type,
        metadata=payload.metadata,
    )


@app.get("/")
def index():
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=404, detail="web/index.html not found")
    return FileResponse(str(INDEX_FILE), media_type="text/html")


@app.head("/")
def index_head():
    if not INDEX_FILE.exists():
        raise HTTPException(status_code=404, detail="web/index.html not found")
    return Response(media_type="text/html")


@app.get("/health")
def health():
    status = STORE.memory_status()
    model_state = LLM.status()
    model_connected = bool(model_state.get("connected"))
    license_state = license_summary()
    public_license_state = {
        "app": license_state.get("app"),
        "licensed": bool(license_state.get("licensed")),
        "expired": bool(license_state.get("expired")),
        "mode": license_state.get("mode"),
        "remaining_seconds": license_state.get("remaining_seconds"),
        "provider": license_state.get("provider"),
        "message": license_state.get("message"),
    }
    public_model_state = {
        "model_id": model_state.get("model_id"),
        "connected": model_connected,
        "reason": model_state.get("reason"),
        "api_url": "local-model-endpoint" if model_connected else "unavailable",
        "context_size": model_state.get("context_size"),
        "mode_policy": model_state.get("mode_policy"),
        "fallback_model": os.getenv("VERITAS_FALLBACK_MODEL", "Qwen3.5-9B-Q4_K_M.gguf"),
    }
    public_status = dict(status or {})
    if isinstance(public_status.get("storage"), dict):
        public_status["storage"] = {
            "memory": "local-managed-storage",
            "vault": "local-managed-storage",
            "knowledge": "local-managed-storage",
        }
    return {
        "ok": True,
        "service": "CLAIRE // VERITAS LEGAL",
        "identity": "Persistent Litigation Intelligence",
        "motto": "Ex Tenebris Iustitia",
        "backend": {"status": "online"},
        "api_url": public_model_state["api_url"],
        "model_id": model_state.get("model_id"),
        "llm_connected": model_connected,
        "model": public_model_state,
        "voice_available": _voice_available(),
        "external_sources": external_source_status(),
        "capabilities": {
            "ocr": _ocr_available(),
            "docx_export": _module_available("docx"),
            "pdf_export": _module_available("fpdf"),
            "voice": _voice_available(),
            "local_folder_import": str(os.getenv("VERITAS_LOCAL_DESKTOP_MODE", "")).strip().lower() in {"1", "true", "yes", "on"},
        },
        "memory": public_status,
        "index": _memory_activity(status),
        "license": public_license_state,
        "veritas_claire_runtime": {
            "enabled": True,
            "scope": "legal evidence intake, workflow guidance, bias guard, trace, and attorney-review packet safety",
        },
        "firm_tier_continuity": build_staff_continuity_status(
            staff_directory=STORE.list_staff_directory(),
            traces=STORE.list_traces(),
            enabled=_firm_tier_continuity_enabled(),
        ),
    }


@app.get("/cases")
def cases():
    return {"items": STORE.list_cases()}


@app.get("/matter")
def matter(case_id: Optional[str] = None):
    return STORE.matter_profile(case_id)


@app.post("/demo-matter")
def demo_matter():
    return seed_harbor_point_demo(STORE)


@app.post("/matter")
def upsert_matter(req: MatterRequest):
    matter = STORE.upsert_matter(
        {
            "case_id": req.case_id,
            "title": req.title,
            "court_profile_id": req.court_profile_id,
            "firm_profile_id": req.firm_profile_id,
            "court_name": req.court_name,
            "district": req.district,
            "jurisdiction": req.jurisdiction,
            "matter_type": req.matter_type,
            "practice_area": req.practice_area,
            "plaintiff": req.plaintiff,
            "defendant": req.defendant,
            "counsel": req.counsel,
            "billing_increment_minutes": req.billing_increment_minutes,
            "billing_rate": req.billing_rate,
            "confidentiality_level": req.confidentiality_level,
            "notes": req.notes,
            "prepared_by_id": req.prepared_by_id,
            "reviewed_by_id": req.reviewed_by_id,
            "approved_by_id": req.approved_by_id,
            "signed_by_id": req.signed_by_id,
            "filed_by_id": req.filed_by_id,
        }
    )
    return {"ok": True, "matter": matter, "bundle": STORE.matter_profile(matter["case_id"])}


@app.get("/firm-profiles")
def firm_profiles():
    return {"items": STORE.list_firm_profiles()}


@app.post("/firm-profile")
def firm_profile(req: FirmProfileRequest):
    record = STORE.upsert_firm_profile(req.dict(exclude_none=True))
    return {"ok": True, "firm_profile": record, "items": STORE.list_firm_profiles()}


@app.get("/staff-directory")
def staff_directory():
    return {"items": STORE.list_staff_directory(), "permissions": FIRM_ROLE_PERMISSIONS}


@app.post("/staff-directory")
def staff_directory_upsert(req: StaffDirectoryRequest):
    record = STORE.upsert_staff_member(req.dict(exclude_none=True))
    return {"ok": True, "staff_member": record, "items": STORE.list_staff_directory()}


@app.get("/authority")
def authority(case_id: Optional[str] = None):
    return STORE.document_authority(case_id)


@app.post("/authority")
def authority_update(req: AuthorityStampRequest):
    matter = STORE.upsert_matter(
        {
            "case_id": req.case_id,
            "firm_profile_id": req.firm_profile_id,
            "prepared_by_id": req.prepared_by_id,
            "reviewed_by_id": req.reviewed_by_id,
            "approved_by_id": req.approved_by_id,
            "signed_by_id": req.signed_by_id,
            "filed_by_id": req.filed_by_id,
            "notes": req.notes,
        }
    )
    authority = STORE.document_authority(matter["case_id"])
    return {"ok": True, "authority": authority, "bundle": STORE.matter_profile(matter["case_id"])}


@app.post("/chat")
def chat(req: ChatRequest):
    global CREATOR_SESSION_UNLOCKED
    query = req.message.strip()
    if not query:
        raise HTTPException(status_code=400, detail="message is required")
    research_intent = _legal_research_intent(query)
    creator_unlock = bool(CREATOR_PASSPHRASE) and query == CREATOR_PASSPHRASE
    if creator_unlock:
        CREATOR_SESSION_UNLOCKED = True
    requested_mode = normalize_chat_mode(req.mode)
    mode = "creator" if CREATOR_SESSION_UNLOCKED and (creator_unlock or requested_mode == "creator") else "legal"
    regulatory_context = _public_regulatory_context(query) if mode == "legal" else {"used": False, "reason": "mode_not_legal", "results": [], "count": 0}
    public_web_context = _public_web_context(query, research_intent) if mode == "legal" else {"used": False, "reason": "mode_not_legal", "results": [], "count": 0}
    recognition_rail = _recognition_rail_context(query, req.case_id, mode, req.top_k)
    analysis_requires_llm = _veritas_thinking_enabled(query, mode)
    COURTLISTENER_LOG.warning(
        "courtlistener.chat_path query=%r intent=%s rail_used=%s rail_reason=%s rail_count=%s returned=%s",
        query,
        research_intent["reason"],
        recognition_rail.get("used"),
        recognition_rail.get("reason"),
        recognition_rail.get("count"),
        len(recognition_rail.get("results") or []),
    )
    bundle_top_k = req.top_k
    if recognition_rail.get("used"):
        bundle_top_k = max(1, min(int(req.top_k or 1), 2))
    bundle = _build_context(query, req.case_id, bundle_top_k)
    effective_max_tokens = int(req.max_tokens or 700)
    if recognition_rail.get("used") and not analysis_requires_llm:
        effective_max_tokens = min(effective_max_tokens, 64)
    if creator_unlock:
        recognition_rail = {
            "used": False,
            "reason": "creator_unlock",
            "query": query,
            "count": 0,
            "results": [],
            "prefix": "",
            "semantic": False,
            "page_size": 0,
        }
        bundle["hits"] = []
        bundle["context_text"] = ""
    if creator_unlock:
        reply = CREATOR_GREETING
    else:
        matter_bundle = STORE.matter_profile(req.case_id)
        runtime_result = VERITAS_RUNTIME.handle_message(
            message=query,
            case_id=req.case_id,
            matter=matter_bundle.get("matter", {}),
            memory_status=STORE.memory_status(),
            citations=bundle.get("hits") or [],
        )
        if runtime_result.reply_override:
            reply = runtime_result.reply_override
            fast_research = False
        else:
            fast_regulatory = bool(regulatory_context.get("used"))
            fast_public_web = bool(public_web_context.get("used")) and not fast_regulatory and not recognition_rail.get("used")
            fast_research = recognition_rail.get("used") and (
                research_intent["matches"]
                or any(
                    marker in query.lower()
                    for marker in ("court", "summary judgment", "opinion", "authority", "precedent", "docket", "what does", "what is", "show me", "where does", "who said")
                )
            ) and not any(marker in query.lower() for marker in ("draft", "write", "memo", "brief", "motion", "argue", "analyze", "compare", "packet"))
            if req.case_id and _local_evidence_support_intent(query) and bundle.get("hits"):
                reply = _fast_matter_evidence_reply(query, bundle, req.case_id)
            elif fast_regulatory and not analysis_requires_llm:
                PUBLIC_RESEARCH_LOG.warning("calregs.synthesis query=%r path=fast_regulatory", query)
                reply = _fast_regulatory_reply(query, regulatory_context)
            elif fast_research and not analysis_requires_llm:
                COURTLISTENER_LOG.warning("courtlistener.synthesis query=%r path=fast_research", query)
                reply = _fast_legal_research_reply(query, bundle, recognition_rail)
            elif fast_public_web and not analysis_requires_llm:
                PUBLIC_RESEARCH_LOG.warning("public_web.synthesis query=%r path=fast_public_web", query)
                reply = _fast_public_web_reply(query, public_web_context)
            elif research_intent["matches"] and regulatory_context.get("reason") == "calregs_error" and not analysis_requires_llm:
                PUBLIC_RESEARCH_LOG.warning("calregs.synthesis query=%r path=regulatory_error", query)
                reply = _fast_regulatory_reply(query, regulatory_context)
            elif research_intent["matches"] and public_web_context.get("reason") == "public_web_error" and not analysis_requires_llm:
                PUBLIC_RESEARCH_LOG.warning("public_web.synthesis query=%r path=web_error", query)
                reply = _fast_public_web_reply(query, public_web_context)
            elif research_intent["matches"] and recognition_rail.get("reason") == "courtlistener_prefetch" and not recognition_rail.get("results") and not analysis_requires_llm:
                COURTLISTENER_LOG.warning("courtlistener.synthesis query=%r path=no_public_match", query)
                reply = (
                    "I searched CourtListener but did not find a matching public case. I also checked the public web research path; no usable public web result was available for synthesis."
                    if public_web_context.get("reason") == "no_public_web_results"
                    else "I searched CourtListener but did not find a matching public case."
                )
            elif research_intent["matches"] and str(recognition_rail.get("reason") or "").startswith("courtlistener_") and not analysis_requires_llm:
                COURTLISTENER_LOG.warning("courtlistener.synthesis query=%r path=research_error", query)
                reply = "I tried to search CourtListener, but the public legal research source is temporarily unavailable. Try again shortly or verify the citation directly in CourtListener."
            else:
                COURTLISTENER_LOG.warning("courtlistener.synthesis query=%r path=llm", query)
                messages = [{"role": "system", "content": build_legal_system_prompt(mode=mode)}]
                if runtime_result.system_context:
                    messages.append({"role": "system", "content": runtime_result.system_context})
                mode_context = build_chat_mode_context(mode=mode)
                if mode_context:
                    messages.append({"role": "system", "content": mode_context})
                if recognition_rail.get("prefix"):
                    messages.append({"role": "system", "content": "Recognition Rail prefetch:\n" + recognition_rail["prefix"]})
                if regulatory_context.get("results"):
                    messages.append({"role": "system", "content": "Public regulation lookup:\n" + json.dumps(regulatory_context.get("results") or [], ensure_ascii=False)})
                if public_web_context.get("results"):
                    messages.append({"role": "system", "content": "Public web research results:\n" + json.dumps(public_web_context.get("results") or [], ensure_ascii=False)})
                if bundle["prefix"]:
                    messages.append({"role": "system", "content": "Matter orientation:\n" + bundle["prefix"]})
                model_thinking_enabled = analysis_requires_llm
                if model_thinking_enabled:
                    effective_max_tokens = max(effective_max_tokens, 700)
                thinking_instruction = (
                    "Model mode: thinking enabled for legal issue analysis. Still do not expose hidden chain-of-thought; provide concise attorney-review analysis."
                    if model_thinking_enabled
                    else "Model mode: non-thinking for retrieval/document summary. Answer directly from sources without internal deliberation."
                )
                messages.append({"role": "system", "content": thinking_instruction})
                messages.extend(
                    [
                        {"role": "system", "content": "Grounded record bundle:\n" + (bundle["context_text"] or "[no matching grounded material]")},
                        {"role": "user", "content": query},
                    ]
                )
                reply = LLM.generate(
                    messages,
                    temperature=req.temperature,
                    max_tokens=effective_max_tokens,
                    thinking_enabled=model_thinking_enabled,
                )
                if runtime_result.user_notice and runtime_result.user_notice.lower() not in str(reply).lower():
                    reply = f"{runtime_result.user_notice}\n\n{reply}".strip()
                if not str(reply or "").strip():
                    reply = _grounded_fallback_reply(query, bundle, req.case_id)
    trace_id = STORE.append_trace(
        {
            "timestamp": time.time(),
            "case_id": req.case_id or "unassigned",
            "event_type": "chat",
            "title": query[:120],
            "summary": reply[:240],
            "metadata": {
                "citations": bundle["hits"][:5],
                "mode": mode,
                "staff_id": req.staff_id,
                "creator_unlock": creator_unlock,
                "recognition_rail": bool(recognition_rail.get("used")),
                "public_regulatory_lookup": regulatory_context,
                "public_web_search": public_web_context,
                "fast_research": bool('fast_research' in locals() and fast_research),
                "model_thinking_enabled": bool(locals().get("model_thinking_enabled", False)),
                "veritas_claire_runtime": runtime_result.to_dict() if 'runtime_result' in locals() else {},
            },
        }
    )
    model_status = LLM.status()
    return {
        "trace_id": trace_id,
        "mode": mode,
        "creator_session": {
            "unlocked": CREATOR_SESSION_UNLOCKED,
            "passphrase_required": bool(CREATOR_PASSPHRASE),
        },
        "reply": reply,
        "citations": bundle["hits"],
        "case_context": _case_context(req.case_id),
        "prompt_prefix": bundle["prefix"],
        "recognition_rail": recognition_rail,
        "public_regulatory_lookup": regulatory_context,
        "public_web_search": public_web_context,
        "veritas_claire_runtime": runtime_result.to_dict() if 'runtime_result' in locals() else {},
        "model": {
            "api_url": "local-model-endpoint" if model_status.get("connected") else "unavailable",
            "model_id": model_status.get("model_id"),
            "connected": bool(model_status.get("connected")),
            "context_size": model_status.get("context_size"),
            "thinking_enabled": bool(locals().get("model_thinking_enabled", False)),
            "mode": "thinking" if locals().get("model_thinking_enabled", False) else "non-thinking",
            "fallback_model": os.getenv("VERITAS_FALLBACK_MODEL", "Qwen3.5-9B-Q4_K_M.gguf"),
        },
    }


@app.post("/search")
def search(req: SearchRequest):
    hits = STORE.search(req.query, case_id=req.case_id, top_k=req.top_k)
    return {"query": req.query, "case_id": req.case_id, "items": hits}


@app.post("/timeline")
def timeline(req: TimelineRequest):
    return {"case_id": req.case_id, "items": STORE.timeline(case_id=req.case_id, limit=req.limit)}


@app.get("/traces")
def traces(case_id: Optional[str] = None, limit: int = 40):
    items = STORE.list_traces(case_id=case_id)
    items = sorted(items, key=lambda item: float(item.get("timestamp", 0)), reverse=True)
    return {"case_id": case_id, "items": items[: max(1, limit)]}


@app.post("/ocr")
def ocr(req: OCRRequest):
    raw = STORE.decode_blob(req.content_b64)
    result = STORE.ocr_image(raw, file_name=req.file_name, mime_type=req.mime_type)
    if result.get("ok"):
        return result
    return JSONResponse(result, status_code=200)


@app.post("/ingest")
def ingest(req: IngestRequest):
    result = _ingest_payload(req)
    source_trace = write_source_trace(
        ROOT,
        build_source_trace(
            source_class="user_evidence",
            action="evidence_ingest",
            query=req.file_name or req.source_type or "manual ingest",
            source_ids={
                "case_id": req.case_id,
                "file_name": req.file_name,
                "source_type": req.source_type,
                "document_id": result.get("document_id") or result.get("id"),
            },
            case_id=req.case_id,
        ),
    )
    result["source_trace"] = source_trace
    return {"ok": True, "result": result, "memory": STORE.memory_status()}


@app.post("/load_corpus")
def load_corpus(req: LoadCorpusRequest):
    result = STORE.load_corpus_folder(req.path, case_id=req.case_id)
    return {"ok": True, "result": result, "memory": STORE.memory_status()}


@app.get("/cache")
def cache():
    return {"items": STORE.cache()}


@app.get("/prompt_prefix")
def prompt_prefix():
    return {"prefix": STORE.prompt_prefix()}


@app.post("/courtlistener/search")
def courtlistener_search(req: CourtListenerSearchRequest):
    try:
        result = VERITAS_COURT_LISTENER.search(
            req.query,
            search_type=req.search_type,
            page_size=req.page_size,
            semantic=req.semantic,
            case_id=req.case_id,
        )
    except requests.HTTPError as exc:  # type: ignore[name-defined]
        status = exc.response.status_code if exc.response is not None else 502
        raise HTTPException(status_code=status, detail=f"CourtListener request failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"CourtListener request failed: {exc}") from exc
    return result


@app.get("/courtlistener/workflow")
def courtlistener_workflow():
    return {
        "configured": VERITAS_COURT_LISTENER.configured(),
        "workflow": VERITAS_COURT_LISTENER.workflow_explanation(),
        "source_classes": {
            "user_evidence": "Uploaded/pasted matter evidence supplied by the user.",
            "courtlistener_public_case_law": "Public case law returned by CourtListener.",
            "recap_docket_or_document_data": "RECAP docket or document data where available.",
            "generated_analysis": "Claire-generated analysis based on grounded sources.",
        },
        "warning": "CourtListener and RECAP data can be partial or stale; verify against the official court docket when currency or completeness matters.",
    }


@app.post("/courtlistener/citation-lookup")
def courtlistener_citation_lookup(req: CourtListenerCitationRequest):
    return VERITAS_COURT_LISTENER.citation_lookup(
        text=req.text,
        volume=req.volume,
        reporter=req.reporter,
        page=req.page,
        case_id=req.case_id,
    )


@app.post("/courtlistener/docket")
def courtlistener_docket(req: CourtListenerLookupRequest):
    return VERITAS_COURT_LISTENER.docket_lookup(req.id, case_id=req.case_id)


@app.post("/courtlistener/recap-document")
def courtlistener_recap_document(req: CourtListenerLookupRequest):
    return VERITAS_COURT_LISTENER.recap_lookup(req.id, case_id=req.case_id)


@app.post("/courtlistener/recap-search")
def courtlistener_recap_search(req: CourtListenerSearchRequest):
    return VERITAS_COURT_LISTENER.recap_search(req.query, page_size=req.page_size, documents_only=req.search_type == "rd", case_id=req.case_id)


@app.post("/courtlistener/ingest")
def courtlistener_ingest(req: CourtListenerIngestRequest):
    try:
        result = VERITAS_COURT_LISTENER.search(
            req.query,
            search_type=req.search_type,
            page_size=req.page_size,
            semantic=req.semantic,
            case_id=req.case_id,
        )
    except requests.HTTPError as exc:  # type: ignore[name-defined]
        status = exc.response.status_code if exc.response is not None else 502
        raise HTTPException(status_code=status, detail=f"CourtListener request failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"CourtListener request failed: {exc}") from exc

    records = COURTLISTENER.build_ingest_records(result)
    imported = []
    for record in records:
        imported.append(
            STORE.ingest_text(
                record["text"],
                case_id=req.case_id,
                case_title=req.case_title,
                source_type="courtlistener",
                file_name=f"{record['title']}.courtlistener.txt",
                mime_type="text/plain",
                metadata=record["metadata"],
            )
        )
    trace_id = STORE.append_trace(
        {
            "timestamp": time.time(),
            "case_id": req.case_id or "unassigned",
            "event_type": "courtlistener_ingest",
            "title": req.query[:120],
            "summary": f"Imported {len(records)} CourtListener result(s) into the active matter.",
            "metadata": {
                "query": req.query,
                "search_type": req.search_type,
                "semantic": req.semantic,
                "courtlistener_traces": result.get("traces") or [],
                "warnings": result.get("warnings") or [],
                "workflow": result.get("workflow"),
            },
        }
    )
    return {
        "ok": True,
        "trace_id": trace_id,
        "query": req.query,
        "imported_count": len(records),
        "results": result["results"],
        "imports": imported,
        "memory": STORE.memory_status(),
    }


@app.get("/edgar/workflow")
def edgar_workflow():
    return {
        "configured": VERITAS_EDGAR.configured(),
        "workflow": VERITAS_EDGAR.workflow_explanation(),
        "source_classes": {
            "sec_edgar_public_filing": "Official SEC EDGAR public company and filing data.",
            "user_evidence": "Uploaded/pasted matter evidence supplied by the user.",
            "generated_analysis": "Claire-generated analysis based on grounded sources.",
        },
        "endpoints": {
            "company_submissions": "https://data.sec.gov/submissions/CIK##########.json",
            "full_text_search": "https://efts.sec.gov/LATEST/search-index",
        },
        "user_agent": VERITAS_EDGAR.client.user_agent,
        "warning": "SEC EDGAR data is external public company/filing material and must be attached or admitted before matter use.",
    }


@app.post("/edgar/search")
def edgar_search(req: EdgarSearchRequest):
    try:
        return VERITAS_EDGAR.search(req.query, page_size=req.page_size, start=req.start, case_id=req.case_id)
    except requests.HTTPError as exc:  # type: ignore[name-defined]
        status = exc.response.status_code if exc.response is not None else 502
        raise HTTPException(status_code=status, detail=f"SEC EDGAR request failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SEC EDGAR request failed: {exc}") from exc


@app.post("/edgar/company-submissions")
def edgar_company_submissions(req: EdgarCompanyRequest):
    try:
        return VERITAS_EDGAR.company_submissions(req.cik, case_id=req.case_id)
    except requests.HTTPError as exc:  # type: ignore[name-defined]
        status = exc.response.status_code if exc.response is not None else 502
        raise HTTPException(status_code=status, detail=f"SEC EDGAR request failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"SEC EDGAR request failed: {exc}") from exc


@app.post("/edgar/ingest")
def edgar_ingest(req: EdgarIngestRequest):
    if req.cik:
        result = VERITAS_EDGAR.company_submissions(req.cik, case_id=req.case_id)
        payload = {"query": req.cik, "filings": result.get("filings") or [], "warnings": result.get("warnings") or []}
    elif req.query:
        result = VERITAS_EDGAR.search(req.query, page_size=req.page_size, start=req.start, case_id=req.case_id)
        payload = result
    else:
        raise HTTPException(status_code=400, detail="Either query or cik is required.")

    records = VERITAS_EDGAR.client.build_ingest_records(payload)
    imported = []
    for record in records:
        imported.append(
            STORE.ingest_text(
                record["text"],
                case_id=req.case_id,
                case_title=req.case_title,
                source_type="sec_edgar",
                file_name=f"{record['title']}.sec-edgar.txt",
                mime_type="text/plain",
                metadata=record["metadata"],
            )
        )
    trace_id = STORE.append_trace(
        {
            "timestamp": time.time(),
            "case_id": req.case_id or "unassigned",
            "event_type": "sec_edgar_ingest",
            "title": (req.query or req.cik or "SEC EDGAR")[:120],
            "summary": f"Imported {len(records)} SEC EDGAR result(s) into the active matter.",
            "metadata": {
                "query": req.query,
                "cik": req.cik,
                "edgar_traces": result.get("traces") or [],
                "warnings": result.get("warnings") or [],
                "workflow": result.get("workflow"),
            },
        }
    )
    return {
        "ok": True,
        "trace_id": trace_id,
        "query": req.query,
        "cik": req.cik,
        "imported_count": len(records),
        "results": result.get("results") or result.get("filings") or [],
        "imports": imported,
        "memory": STORE.memory_status(),
    }


@app.post("/suggest")
def suggest(req: SuggestRequest):
    return {"query": req.query, "items": STORE.search(req.query, case_id=req.case_id, top_k=req.top_k)}


@app.post("/analyze")
def analyze(req: AnalysisRequest):
    result = STORE.analyze_matter(query=req.query, case_id=req.case_id, top_k=req.top_k)
    source_trace = write_source_trace(
        ROOT,
        build_source_trace(
            source_class="generated_analysis",
            action="matter_analysis",
            query=req.query,
            source_ids={"case_id": req.case_id, "records": len(result.get("records") or [])},
            warnings=[{"code": "generated_analysis_review", "message": "Generated analysis must be reviewed against cited source material and attorney judgment."}],
            case_id=req.case_id,
        ),
    )
    trace_id = STORE.append_trace(
        {
            "timestamp": time.time(),
            "case_id": req.case_id or result["matter"].get("case_id", "unassigned"),
            "event_type": "analysis",
            "title": "Matter analysis",
            "summary": result["scenarios"][0]["summary"] if result["scenarios"] else "Matter analysis complete.",
            "metadata": {
                "anomalies": result["anomalies"],
                "filings": result["filing_suggestions"],
                "billing": result["billing"],
                "source_trace": source_trace,
            },
        }
    )
    return {"trace_id": trace_id, **result}


@app.get("/court-profiles")
def court_profiles():
    return {"items": STORE.list_court_profiles()}


@app.post("/court-profiles")
def upsert_court_profile(req: CourtProfileRequest):
    payload = {k: v for k, v in req.model_dump().items() if v is not None}
    profile = STORE.upsert_court_profile(payload)
    return {"ok": True, "profile": profile, "report": build_court_profile_report(profile)}


@app.get("/court-profile-report")
def court_profile_report(case_id: Optional[str] = None):
    bundle = STORE.matter_profile(case_id)
    return bundle.get("court_profile_report", {})


@app.post("/court-rules/load")
def load_court_rules(req: CourtRulesLoadRequest):
    result = STORE.load_court_rules_folder(req.path)
    return {"ok": True, "result": result, "court_profiles": STORE.list_court_profiles()}


@app.get("/docket-events")
def docket_events(case_id: Optional[str] = None):
    return {"items": STORE.list_dockets(case_id=case_id)}


@app.post("/docket/import")
def import_docket(req: DocketImportRequest):
    payload: Any = req.payload
    if req.content_b64:
        try:
            raw = base64.b64decode(req.content_b64)
            text = raw.decode("utf-8", errors="ignore")
            payload = text
        except Exception:
            payload = req.text or req.payload or ""
    elif req.path:
        path = Path(req.path)
        if not path.is_absolute():
            path = (ROOT / path).resolve()
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"Docket source not found: {path}")
        payload = path.read_text(encoding="utf-8", errors="ignore")
    elif req.text is not None:
        payload = req.text
    result = STORE.import_docket_payload(payload, case_id=req.case_id, court_name=req.court_name, source_name=req.source_name)
    return {"ok": True, "result": result, "bundle": STORE.matter_profile(result["matter"]["case_id"])}


@app.get("/filing-templates")
def filing_templates():
    return {"items": STORE.matter_profile(None).get("templates", [])}


@app.post("/draft")
def draft(req: DraftRequest):
    packet = STORE.build_packet(template_id=req.template_id, case_id=req.case_id, query=req.query)
    draft_text = "\n\n".join(packet["sections"])
    source_trace = write_source_trace(
        ROOT,
        build_source_trace(
            source_class="generated_analysis",
            action="attorney_review_packet_draft",
            query=req.query,
            source_ids={"case_id": req.case_id, "template_id": req.template_id},
            warnings=[{"code": "attorney_review_required", "message": "Packet drafts organize source material but do not replace attorney review."}],
            case_id=req.case_id,
        ),
    )
    trace_id = STORE.append_trace(
        {
            "timestamp": time.time(),
            "case_id": req.case_id or packet["matter"].get("case_id", "unassigned"),
            "event_type": "draft",
            "title": packet["template"]["title"],
            "summary": packet["scenarios"][0]["summary"] if packet["scenarios"] else "Draft packet generated.",
            "metadata": {"template_id": req.template_id, "court_profile": packet["court_profile"], "source_trace": source_trace},
        }
    )
    return {"trace_id": trace_id, "packet": packet, "draft_text": draft_text}


@app.post("/export_packet")
def export_packet(req: ExportRequest):
    packet = STORE.build_packet(template_id=req.template_id, case_id=req.case_id, query=req.query)
    if packet.get("authority", {}).get("violations"):
        raise HTTPException(status_code=409, detail={"message": "Document authority assignments are invalid.", "violations": packet["authority"]["violations"]})
    markdown = packet_to_markdown(packet, redact=req.redact)
    filename = f"{packet['matter'].get('case_id', 'unassigned')}_{packet['template'].get('id', 'packet')}.md"
    return {
        "filename": filename,
        "format": req.format,
        "redacted": req.redact,
        "packet": packet,
        "markdown": markdown,
    }


@app.post("/export_packet_docx")
def export_packet_docx(req: ExportRequest):
    packet = STORE.build_packet(template_id=req.template_id, case_id=req.case_id, query=req.query)
    if packet.get("authority", {}).get("violations"):
        raise HTTPException(status_code=409, detail={"message": "Document authority assignments are invalid.", "violations": packet["authority"]["violations"]})
    docx_bytes = packet_to_docx_bytes(packet, redact=req.redact)
    filename = f"{packet['matter'].get('case_id', 'unassigned')}_{packet['template'].get('id', 'packet')}.docx"
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/export_packet_pdf")
def export_packet_pdf(req: ExportRequest):
    packet = STORE.build_packet(template_id=req.template_id, case_id=req.case_id, query=req.query)
    if packet.get("authority", {}).get("violations"):
        raise HTTPException(status_code=409, detail={"message": "Document authority assignments are invalid.", "violations": packet["authority"]["violations"]})
    try:
        pdf_bytes = packet_to_pdf_bytes(packet, redact=req.redact)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    filename = f"{packet['matter'].get('case_id', 'unassigned')}_{packet['template'].get('id', 'packet')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/packet_scan")
def packet_scan(req: DraftRequest):
    packet = STORE.build_packet(template_id=req.template_id, case_id=req.case_id, query=req.query)
    return {"scan": scan_packet(packet), "packet": packet}


@app.post("/billing_estimate")
def billing_estimate(req: BillingRequest):
    matter = STORE.upsert_matter(
        {
            "case_id": req.case_id,
            "billing_increment_minutes": int(req.billing_increment_minutes or 15),
            "billing_rate": float(req.billing_rate if req.billing_rate is not None else 0.0),
        }
    )
    result = STORE.matter_profile(req.case_id)
    estimate = STORE.analyze_matter(query=req.task_description or "billing estimate", case_id=req.case_id, top_k=5)["billing"]
    return {"matter": matter, "bundle": result, "estimate": estimate}


@app.get("/gyro_debug")
def gyro_debug():
    return {"weights": {"semantic": 0.40, "temporal": 0.20, "intent": 0.25, "priority": 0.15}, "memory": STORE.memory_status(), "cache": STORE.cache(), "prompt_prefix": STORE.prompt_prefix()}


@app.post("/gyro")
def gyro(req: GyroRequest):
    result = STORE.stabilize_vision(req.input, case_id=req.case_id, top_k=req.top_k, ingest=req.ingest_input)
    trace_id = STORE.append_trace(
        {
            "timestamp": time.time(),
            "case_id": req.case_id or "unassigned",
            "event_type": "gyro",
            "title": req.input[:120],
            "summary": result["visor"][:240],
            "metadata": {"semantic_velocity": result["semantic_velocity"], "items": result["items"][:5]},
        }
    )
    return {"trace_id": trace_id, **result}


@app.get("/are/debug")
def are_debug():
    return gyro_debug()


@app.get("/recognition-rail/debug")
def recognition_rail_debug():
    return gyro_debug()


@app.post("/are/stabilize")
def are_stabilize(req: GyroRequest):
    return gyro(req)


@app.post("/recognition-rail/stabilize")
def recognition_rail_stabilize(req: GyroRequest):
    return gyro(req)


@app.post("/prompt-prefix")
def prompt_prefix_demo(req: PromptPrefixRequest):
    result = STORE.generate_gyro_prompt(req.input, system_instruction=req.system_instruction, case_id=req.case_id, top_k=req.top_k, ingest=req.ingest_input)
    trace_id = STORE.append_trace(
        {
            "timestamp": time.time(),
            "case_id": req.case_id or "unassigned",
            "event_type": "prompt_prefix",
            "title": req.input[:120],
            "summary": result["prompt"][:240],
            "metadata": {"semantic_velocity": result["semantic_velocity"], "items": result["items"][:5]},
        }
    )
    return {"trace_id": trace_id, **result}


@app.post("/are/prompt-prefix")
def are_prompt_prefix_demo(req: PromptPrefixRequest):
    return prompt_prefix_demo(req)


@app.post("/recognition-rail/prompt-prefix")
def recognition_rail_prompt_prefix_demo(req: PromptPrefixRequest):
    return prompt_prefix_demo(req)


@app.post("/are/courtlistener-prefix")
def are_courtlistener_prefix(req: CourtListenerSearchRequest):
    payload = _build_recognition_rail_prefix(
        req.query,
        search_type=req.search_type,
        page_size=req.page_size,
        semantic=req.semantic,
    )
    return {"query": req.query, **payload}


@app.post("/recognition-rail/courtlistener-prefix")
def recognition_rail_courtlistener_prefix(req: CourtListenerSearchRequest):
    return are_courtlistener_prefix(req)


@app.post("/query")
def query(req: SearchRequest):
    return search(req)


@app.get("/trace/{trace_id}")
def trace(trace_id: str):
    payload = STORE.read_trace(trace_id)
    if not payload:
        raise HTTPException(status_code=404, detail="Trace not found.")
    return payload


@app.get("/report/{trace_id}", response_class=PlainTextResponse)
def report(trace_id: str):
    report_text = STORE.trace_report(trace_id)
    if not report_text:
        raise HTTPException(status_code=404, detail="Trace not found.")
    return report_text


@app.post("/demo")
def demo(req: GyroRequest):
    if req.input.strip().lower() in {"", "demo"}:
        req.input = "Show how ARE Glasses improves an AI answer about a remembered safety note."
    return gyro(req)


@app.get("/are/health")
def are_health():
    return health()


@app.post("/are/ingest")
def are_ingest(req: IngestRequest):
    return ingest(req)


@app.post("/are/query")
def are_query(req: SearchRequest):
    return search(req)


@app.post("/are/load-corpus")
def are_load_corpus(req: LoadCorpusRequest):
    return load_corpus(req)


@app.get("/are/cache")
def are_cache():
    return cache()


@app.get("/are/prompt-prefix")
def are_prompt_prefix():
    return prompt_prefix()


@app.post("/are/suggest")
def are_suggest(req: SuggestRequest):
    return suggest(req)


@app.post("/are/gyro")
def are_gyro(req: GyroRequest):
    return gyro(req)


@app.websocket("/ws/ingest")
async def ws_ingest(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"text": raw}
            req = IngestRequest(**payload)
            result = _ingest_payload(req)
            await websocket.send_json({"ok": True, "result": result, "memory": STORE.memory_status()})
    except WebSocketDisconnect:
        return


@app.on_event("startup")
def _startup():
    ensure_license()
    STORE.memory_status()


def _voice_available() -> bool:
    try:
        import voice_input  # noqa: F401
        import voice_output  # noqa: F401
        return True
    except Exception:
        return False
from fastapi import Request
from fastapi.responses import JSONResponse


@app.get("/license/status")
def get_license_status():
    ensure_license()
    return license_summary()


@app.post("/license/activate")
def post_license_activate(payload: dict):
    token = str(payload.get("token", "")).strip()
    provider = str(payload.get("provider", "manual")).strip() or "manual"
    if not token:
        raise HTTPException(status_code=400, detail="License token is required.")
    try:
        record = activate_license(token=token, provider=provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "ok": True,
        "license": record,
        "status": license_summary(),
    }


@app.get("/license/evaluation")
def get_license_evaluation():
    status = verify_license()
    return {
        "mode": status.mode,
        "licensed": status.licensed,
        "expired": status.expired,
        "remaining_seconds": status.remaining_seconds,
        "message": status.message,
    }


@app.middleware("http")
async def evaluation_license_guard(request: Request, call_next):
    status = verify_license()
    if status.expired:
        blocked_paths = {
            "/chat",
            "/ingest",
            "/load_corpus",
            "/ocr",
            "/suggest",
            "/ws/ingest",
            "/are/ingest",
            "/are/load-corpus",
            "/are/suggest",
        }
        if request.url.path in blocked_paths and request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            return JSONResponse(
                status_code=403,
                content={
                    "ok": False,
                    "read_only": True,
                    "detail": "Evaluation period expired. Continue Read-Only or activate a Professional License.",
                },
            )
    return await call_next(request)
