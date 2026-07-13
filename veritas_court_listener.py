from __future__ import annotations

from pathlib import Path
from typing import Any

from courtlistener_client import CourtListenerClient, CourtListenerRateLimitError, source_class_for_search_type
from veritas_source_trace import build_source_trace, write_source_trace


class VeritasCourtListener:
    def __init__(self, root: str | Path, client: CourtListenerClient | None = None):
        self.root = Path(root)
        self.client = client or CourtListenerClient()

    def configured(self) -> bool:
        return self.client.configured()

    def workflow_explanation(self) -> str:
        return (
            "Court Listener workflow: I can search CourtListener public case law, RECAP docket/document data, and docket metadata. "
            "I will tell you what source class I am searching, keep user-provided evidence separate from public legal materials, "
            "trace CourtListener URLs and IDs, and warn when results are partial, stale, missing documents, or rate-limited. "
            "CourtListener and RECAP are public legal-data sources, not a substitute for checking the official court docket when verification matters."
        )

    def search(self, query: str, *, search_type: str = "o", page_size: int = 5, semantic: bool = False, case_id: str | None = None) -> dict[str, Any]:
        try:
            payload = self.client.search(query, search_type=search_type, page_size=page_size, semantic=semantic)
        except CourtListenerRateLimitError as exc:
            return self._rate_limited("search", query, search_type, case_id, exc)
        payload["workflow"] = self.workflow_explanation()
        payload["source_class"] = source_class_for_search_type(search_type)
        payload["configured"] = self.configured()
        payload["public_access"] = not self.configured()
        payload["traces"] = self._trace_results(payload, action="courtlistener_search", case_id=case_id)
        return payload

    def citation_lookup(self, *, text: str | None = None, volume: str | None = None, reporter: str | None = None, page: str | None = None, case_id: str | None = None) -> dict[str, Any]:
        query = text or " ".join(part for part in [volume, reporter, page] if part)
        try:
            payload = self.client.citation_lookup(text=text, volume=volume, reporter=reporter, page=page)
        except CourtListenerRateLimitError as exc:
            return self._rate_limited("citation_lookup", query, "citation_lookup", case_id, exc)
        trace = build_source_trace(
            source_class="courtlistener_public_case_law",
            action="citation_lookup",
            query=query,
            warnings=payload.get("warnings") or [],
            case_id=case_id,
        )
        payload["workflow"] = self.workflow_explanation()
        payload["configured"] = self.configured()
        payload["public_access"] = not self.configured()
        payload["trace"] = write_source_trace(self.root, trace)
        return payload

    def docket_lookup(self, docket_id: int | str, *, case_id: str | None = None) -> dict[str, Any]:
        if not self.configured():
            return self._not_configured("docket_lookup", str(docket_id), "docket", case_id)
        try:
            payload = self.client.get_docket(docket_id)
        except CourtListenerRateLimitError as exc:
            return self._rate_limited("docket_lookup", str(docket_id), "docket", case_id, exc)
        docket = payload.get("docket") or {}
        trace = build_source_trace(
            source_class="courtlistener_public_docket_metadata",
            action="docket_lookup",
            query=str(docket_id),
            source_url=docket.get("absolute_url") or docket.get("resource_uri"),
            source_ids={"docket_id": docket.get("id") or docket_id},
            warnings=payload.get("warnings") or [],
            case_id=case_id,
        )
        payload["workflow"] = self.workflow_explanation()
        payload["trace"] = write_source_trace(self.root, trace)
        return payload

    def recap_lookup(self, document_id: int | str, *, case_id: str | None = None) -> dict[str, Any]:
        if not self.configured():
            return self._not_configured("recap_lookup", str(document_id), "recap_document", case_id)
        try:
            payload = self.client.get_recap_document(document_id)
        except CourtListenerRateLimitError as exc:
            return self._rate_limited("recap_lookup", str(document_id), "recap_document", case_id, exc)
        document = payload.get("recap_document") or {}
        trace = build_source_trace(
            source_class="recap_docket_or_document_data",
            action="recap_lookup",
            query=str(document_id),
            source_url=document.get("absolute_url") or document.get("filepath_ia") or document.get("resource_uri"),
            source_ids={"recap_document_id": document.get("id") or document_id, "docket_id": document.get("docket")},
            warnings=payload.get("warnings") or [],
            case_id=case_id,
        )
        payload["workflow"] = self.workflow_explanation()
        payload["trace"] = write_source_trace(self.root, trace)
        return payload

    def recap_search(self, query: str, *, page_size: int = 5, documents_only: bool = False, case_id: str | None = None) -> dict[str, Any]:
        return self.search(query, search_type="rd" if documents_only else "r", page_size=page_size, case_id=case_id)

    def _trace_results(self, payload: dict[str, Any], *, action: str, case_id: str | None) -> list[dict[str, Any]]:
        traces = []
        source_class = payload.get("source_class") or source_class_for_search_type(payload.get("search_type"))
        for item in payload.get("results") or []:
            trace = build_source_trace(
                source_class=source_class,
                action=action,
                query=payload.get("query") or "",
                source_url=item.get("source_url"),
                source_ids=item.get("source_ids") or {},
                warnings=(payload.get("warnings") or []) + (item.get("warnings") or []),
                case_id=case_id,
            )
            traces.append(write_source_trace(self.root, trace))
        if not traces:
            trace = build_source_trace(
                source_class=source_class,
                action=action,
                query=payload.get("query") or "",
                warnings=payload.get("warnings") or [],
                case_id=case_id,
            )
            traces.append(write_source_trace(self.root, trace))
        return traces

    def _not_configured(self, action: str, query: str, search_type: str, case_id: str | None) -> dict[str, Any]:
        warning = {"code": "courtlistener_not_configured", "message": "COURTLISTENER_TOKEN is not configured; CourtListener access is disabled."}
        source_class = "courtlistener_public_case_law" if search_type == "citation_lookup" else source_class_for_search_type(search_type)
        trace = build_source_trace(
            source_class=source_class,
            action=action,
            query=query,
            warnings=[warning],
            case_id=case_id,
        )
        return {
            "configured": False,
            "ok": False,
            "query": query,
            "results": [],
            "warnings": [warning],
            "workflow": self.workflow_explanation(),
            "trace": write_source_trace(self.root, trace),
        }

    def _rate_limited(self, action: str, query: str, search_type: str, case_id: str | None, exc: CourtListenerRateLimitError) -> dict[str, Any]:
        warning = {
            "code": "courtlistener_rate_limited",
            "message": "CourtListener rate limit reached; wait before retrying.",
            "wait_seconds": exc.wait_seconds,
        }
        trace = build_source_trace(
            source_class="courtlistener_public_case_law" if search_type == "citation_lookup" else source_class_for_search_type(search_type),
            action=action,
            query=query,
            warnings=[warning],
            case_id=case_id,
        )
        return {
            "configured": True,
            "ok": False,
            "query": query,
            "results": [],
            "warnings": [warning],
            "workflow": self.workflow_explanation(),
            "trace": write_source_trace(self.root, trace),
        }
