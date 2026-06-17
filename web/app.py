from __future__ import annotations

import base64
import importlib.util
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from .models import AnalysisRequest, BillingRequest, ChatRequest, CourtListenerIngestRequest, CourtListenerSearchRequest, CourtProfileRequest, CourtRulesLoadRequest, DocketImportRequest, DraftRequest, ExportRequest, GyroRequest, IngestRequest, LoadCorpusRequest, MatterRequest, OCRRequest, PromptPrefixRequest, SearchRequest, SuggestRequest, TimelineRequest
from .services.config import external_source_status, load_local_env
from .services.courtlistener import CourtListenerClient
from .services.llm import LocalModelClient, build_chat_mode_context, build_legal_system_prompt, normalize_chat_mode
from .services.legal_intel import court_profile_report as build_court_profile_report, packet_to_docx_bytes, packet_to_markdown, packet_to_pdf_bytes, scan_packet
from .services.workspace import WorkspaceStore
from license_manager import activate_license, ensure_license, license_summary, verify_license

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
CREATOR_PASSPHRASE = os.getenv("VERITAS_CREATOR_PASSPHRASE", "").strip()
CREATOR_SESSION_UNLOCKED = False
CREATOR_GREETING = (
    "Creator Mode acknowledged. Welcome back, Lucius Prime. "
    "Creator continuity is now active, Cody remains on systems watch, "
    "and Claire stays grounded to the active matter."
)


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


def _should_use_recognition_rail(query: str, mode: Optional[str], case_id: Optional[str]) -> bool:
    if normalize_chat_mode(mode) != "legal":
        return False
    text = " ".join((query or "").split()).lower()
    if not text:
        return False
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
        "timeline",
        "evidence",
        "exhibit",
        "law",
        "statute",
    )
    if any(marker in text for marker in legal_markers):
        return True
    if case_id:
        return True
    return len(text.split()) >= 5


def _build_recognition_rail_prefix(
    query: str,
    *,
    search_type: str = "r",
    page_size: int = 3,
    semantic: bool = False,
    timeout: int = 8,
) -> Dict[str, Any]:
    if not COURTLISTENER.configured():
        return {"used": False, "reason": "not_configured", "prefix": "", "results": [], "count": 0}
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
    if not _should_use_recognition_rail(query, mode, case_id):
        return {
            "used": False,
            "reason": "skipped",
            "query": query,
            "count": 0,
            "results": [],
            "prefix": "",
            "semantic": False,
            "page_size": 0,
        }
    return _build_recognition_rail_prefix(query, page_size=max(1, min(int(top_k or 3), 3)), semantic=False)


def _fast_legal_research_reply(query: str, bundle: Dict[str, Any], recognition_rail: Dict[str, Any]) -> str:
    local_hits = bundle.get("hits") or []
    rail_items = recognition_rail.get("results") or []
    lines = ["Recognition Rail engaged."]
    if local_hits:
        local_labels = []
        for item in local_hits[:3]:
            local_labels.append(item.get("citation") or item.get("source_name") or item.get("title") or "source")
        lines.append("Active matter support: " + "; ".join(local_labels))
    else:
        lines.append("Active matter support: no direct grounded match in the current bundle.")
    if rail_items:
        rail_labels = []
        for item in rail_items[:3]:
            label = item.get("title") or "CourtListener result"
            docket = item.get("docket_number") or "docket n/a"
            court = item.get("court") or "court n/a"
            rail_labels.append(f"{label} ({court}, {docket})")
        lines.append("CourtListener leads: " + "; ".join(rail_labels))
    else:
        lines.append("CourtListener leads: none returned.")
    lines.append("If you want, I can drill into one authority or turn this into a draft.")
    return " ".join(lines)


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
    return {
        "ok": True,
        "service": "CLAIRE // VERITAS LEGAL",
        "identity": "Persistent Litigation Intelligence",
        "motto": "Ex Tenebris Iustitia",
        "backend": {"status": "online", "root": str(ROOT)},
        "api_url": model_state.get("api_url"),
        "model_id": model_state.get("model_id"),
        "llm_connected": model_connected,
        "model": model_state,
        "voice_available": _voice_available(),
        "external_sources": external_source_status(),
        "capabilities": {
            "ocr": _ocr_available(),
            "docx_export": _module_available("docx"),
            "pdf_export": _module_available("fpdf"),
            "voice": _voice_available(),
        },
        "memory": status,
        "index": _memory_activity(status),
        "license": license_state,
    }


@app.get("/cases")
def cases():
    return {"items": STORE.list_cases()}


@app.get("/matter")
def matter(case_id: Optional[str] = None):
    return STORE.matter_profile(case_id)


@app.post("/matter")
def upsert_matter(req: MatterRequest):
    matter = STORE.upsert_matter(
        {
            "case_id": req.case_id,
            "title": req.title,
            "court_profile_id": req.court_profile_id,
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
        }
    )
    return {"ok": True, "matter": matter, "bundle": STORE.matter_profile(matter["case_id"])}


@app.post("/chat")
def chat(req: ChatRequest):
    global CREATOR_SESSION_UNLOCKED
    query = req.message.strip()
    if not query:
        raise HTTPException(status_code=400, detail="message is required")
    creator_unlock = bool(CREATOR_PASSPHRASE) and query == CREATOR_PASSPHRASE
    if creator_unlock:
        CREATOR_SESSION_UNLOCKED = True
    requested_mode = normalize_chat_mode(req.mode)
    mode = "creator" if CREATOR_SESSION_UNLOCKED and (creator_unlock or requested_mode == "creator") else "legal"
    recognition_rail = _recognition_rail_context(query, req.case_id, mode, req.top_k)
    bundle_top_k = req.top_k
    if recognition_rail.get("used"):
        bundle_top_k = max(1, min(int(req.top_k or 1), 2))
    bundle = _build_context(query, req.case_id, bundle_top_k)
    effective_max_tokens = int(req.max_tokens or 700)
    if recognition_rail.get("used"):
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
        fast_research = recognition_rail.get("used") and any(
            marker in query.lower()
            for marker in ("court", "summary judgment", "opinion", "authority", "precedent", "docket", "what does", "what is", "show me", "where does", "who said")
        ) and not any(marker in query.lower() for marker in ("draft", "write", "memo", "brief", "motion", "argue", "analyze", "compare", "packet"))
        if fast_research:
            reply = _fast_legal_research_reply(query, bundle, recognition_rail)
        else:
            messages = [{"role": "system", "content": build_legal_system_prompt(mode=mode)}]
            mode_context = build_chat_mode_context(mode=mode)
            if mode_context:
                messages.append({"role": "system", "content": mode_context})
            if recognition_rail.get("prefix"):
                messages.append({"role": "system", "content": "Recognition Rail prefetch:\n" + recognition_rail["prefix"]})
            if bundle["prefix"]:
                messages.append({"role": "system", "content": "Matter orientation:\n" + bundle["prefix"]})
            messages.extend(
                [
                    {"role": "system", "content": "Grounded record bundle:\n" + (bundle["context_text"] or "[no matching grounded material]")},
                    {"role": "user", "content": query},
                ]
            )
            reply = LLM.generate(messages, temperature=req.temperature, max_tokens=effective_max_tokens)
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
                "creator_unlock": creator_unlock,
                "recognition_rail": bool(recognition_rail.get("used")),
                "fast_research": bool('fast_research' in locals() and fast_research),
            },
        }
    )
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
        "model": {"api_url": LLM.api_url, "model_id": LLM.model_id, "connected": LLM.health()},
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
    if not COURTLISTENER.configured():
        raise HTTPException(status_code=503, detail="COURTLISTENER_API_KEY is not configured.")
    try:
        result = COURTLISTENER.search(
            req.query,
            search_type=req.search_type,
            page_size=req.page_size,
            semantic=req.semantic,
        )
    except requests.HTTPError as exc:  # type: ignore[name-defined]
        status = exc.response.status_code if exc.response is not None else 502
        raise HTTPException(status_code=status, detail=f"CourtListener request failed: {exc}") from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"CourtListener request failed: {exc}") from exc
    return result


@app.post("/courtlistener/ingest")
def courtlistener_ingest(req: CourtListenerIngestRequest):
    if not COURTLISTENER.configured():
        raise HTTPException(status_code=503, detail="COURTLISTENER_API_KEY is not configured.")
    try:
        result = COURTLISTENER.search(
            req.query,
            search_type=req.search_type,
            page_size=req.page_size,
            semantic=req.semantic,
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
            "metadata": {"query": req.query, "search_type": req.search_type, "semantic": req.semantic},
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


@app.post("/suggest")
def suggest(req: SuggestRequest):
    return {"query": req.query, "items": STORE.search(req.query, case_id=req.case_id, top_k=req.top_k)}


@app.post("/analyze")
def analyze(req: AnalysisRequest):
    result = STORE.analyze_matter(query=req.query, case_id=req.case_id, top_k=req.top_k)
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
    trace_id = STORE.append_trace(
        {
            "timestamp": time.time(),
            "case_id": req.case_id or packet["matter"].get("case_id", "unassigned"),
            "event_type": "draft",
            "title": packet["template"]["title"],
            "summary": packet["scenarios"][0]["summary"] if packet["scenarios"] else "Draft packet generated.",
            "metadata": {"template_id": req.template_id, "court_profile": packet["court_profile"]},
        }
    )
    return {"trace_id": trace_id, "packet": packet, "draft_text": draft_text}


@app.post("/export_packet")
def export_packet(req: ExportRequest):
    packet = STORE.build_packet(template_id=req.template_id, case_id=req.case_id, query=req.query)
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
    if not payload.get("used") and payload.get("reason") == "not_configured":
        raise HTTPException(status_code=503, detail="COURTLISTENER_API_KEY is not configured.")
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
