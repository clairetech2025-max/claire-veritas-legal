from __future__ import annotations

import html
import os
import re
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Dict, Optional

import requests


API_ROOT = "https://www.courtlistener.com/api/rest/v4"


class CourtListenerRateLimitError(RuntimeError):
    def __init__(self, message: str, *, wait_seconds: float | None = None, response_json: dict[str, Any] | None = None):
        super().__init__(message)
        self.wait_seconds = wait_seconds
        self.response_json = response_json or {}


@dataclass
class CourtListenerWarning:
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def strip_markup(text: str) -> str:
    return re.sub(r"<[^>]+>", "", html.unescape(text or "")).strip()


def _retry_after_seconds(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(value)
        return max(0.0, dt.timestamp() - time.time())
    except Exception:
        return None


def _wait_until_seconds(payload: dict[str, Any]) -> float | None:
    value = payload.get("wait_until") or payload.get("wait_util")
    if not value:
        return None
    try:
        normalized = str(value).replace("Z", "+00:00")
        from datetime import datetime

        dt = datetime.fromisoformat(normalized)
        return max(0.0, dt.timestamp() - time.time())
    except Exception:
        return None


class CourtListenerClient:
    def __init__(
        self,
        token: Optional[str] = None,
        api_root: str = API_ROOT,
        *,
        session: Any | None = None,
        min_interval_seconds: float = 0.25,
        max_retries: int = 2,
        max_backoff_seconds: float = 8.0,
    ):
        self.token = (token or os.getenv("COURTLISTENER_TOKEN") or os.getenv("COURTLISTENER_API_KEY") or "").strip()
        self.api_root = api_root.rstrip("/")
        self.session = session or requests.Session()
        self.min_interval_seconds = max(0.0, float(min_interval_seconds))
        self.max_retries = max(0, int(max_retries))
        self.max_backoff_seconds = max(0.0, float(max_backoff_seconds))
        self._last_request_at = 0.0

    @property
    def api_key(self) -> str:
        return self.token

    def configured(self) -> bool:
        return bool(self.token)

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.configured():
            headers["Authorization"] = f"Token {self.token}"
        return headers

    def _sleep_for_client_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)
        self._last_request_at = time.monotonic()

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> dict[str, Any] | list[Any]:
        url = path if path.startswith("https://") else f"{self.api_root}/{path.strip('/')}/"
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._sleep_for_client_rate_limit()
            response = self.session.request(
                method.upper(),
                url,
                headers=self._headers(),
                params=params,
                data=data,
                timeout=max(1, int(timeout or 30)),
            )
            if response.status_code == 429:
                payload: dict[str, Any] = {}
                try:
                    payload = response.json()
                except Exception:
                    payload = {}
                wait_seconds = _retry_after_seconds(response.headers.get("Retry-After")) or _wait_until_seconds(payload)
                if attempt < self.max_retries:
                    time.sleep(min(wait_seconds or (2 ** attempt), self.max_backoff_seconds))
                    continue
                raise CourtListenerRateLimitError("CourtListener rate limit reached.", wait_seconds=wait_seconds, response_json=payload)
            try:
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries and response.status_code in {500, 502, 503, 504}:
                    time.sleep(min(2 ** attempt, self.max_backoff_seconds))
                    continue
                raise
        raise RuntimeError(f"CourtListener request failed: {last_exc}")

    def search(
        self,
        query: str,
        *,
        search_type: str = "o",
        page_size: int = 5,
        semantic: bool = False,
        timeout: int = 30,
        order_by: str | None = None,
    ) -> Dict[str, Any]:
        params: dict[str, Any] = {
            "q": query,
            "type": search_type or "o",
            "page_size": max(1, min(int(page_size or 5), 20)),
        }
        if semantic:
            params["semantic"] = "true"
        if order_by:
            params["order_by"] = order_by
        payload = self._request("GET", "search", params=params, timeout=timeout)
        if not isinstance(payload, dict):
            raise RuntimeError("CourtListener search returned non-object JSON.")
        results = [self._normalize_result(item, params["type"]) for item in payload.get("results") or []]
        results = results[: params["page_size"]]
        warnings = self._search_warnings(payload, params["type"], results)
        return {
            "query": query,
            "search_type": params["type"],
            "page_size": params["page_size"],
            "semantic": semantic,
            "count": payload.get("count", len(results)),
            "document_count": payload.get("document_count"),
            "results": results,
            "warnings": [warning.to_dict() for warning in warnings],
            "next": payload.get("next"),
            "previous": payload.get("previous"),
            "authenticated": self.configured(),
        }

    def citation_lookup(
        self,
        *,
        text: str | None = None,
        volume: str | None = None,
        reporter: str | None = None,
        page: str | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if text:
            data["text"] = text[:64000]
        else:
            data = {"volume": volume or "", "reporter": reporter or "", "page": page or ""}
        payload = self._request("POST", "citation-lookup", data=data, timeout=timeout)
        if not isinstance(payload, list):
            raise RuntimeError("CourtListener citation lookup returned non-list JSON.")
        warnings = []
        for item in payload:
            status = int((item or {}).get("status") or 0)
            if status == 404:
                warnings.append(CourtListenerWarning("citation_not_found", f"Citation not found: {(item or {}).get('citation') or 'unknown'}"))
            elif status == 300:
                warnings.append(CourtListenerWarning("ambiguous_citation", f"Citation matched multiple cases: {(item or {}).get('citation') or 'unknown'}"))
            elif status == 429:
                warnings.append(CourtListenerWarning("citation_lookup_limited", f"Citation parsed but not fully looked up: {(item or {}).get('citation') or 'unknown'}"))
        return {
            "results": payload,
            "warnings": [warning.to_dict() for warning in warnings],
            "source_type": "courtlistener_citation_lookup",
            "authenticated": self.configured(),
        }

    def get_docket(self, docket_id: int | str, *, timeout: int = 30) -> dict[str, Any]:
        payload = self._request("GET", f"dockets/{docket_id}", timeout=timeout)
        if not isinstance(payload, dict):
            raise RuntimeError("CourtListener docket lookup returned non-object JSON.")
        return {"docket": payload, "warnings": self._docket_warnings(payload), "source_type": "courtlistener_docket"}

    def get_recap_document(self, document_id: int | str, *, timeout: int = 30) -> dict[str, Any]:
        payload = self._request("GET", f"recap-documents/{document_id}", timeout=timeout)
        if not isinstance(payload, dict):
            raise RuntimeError("CourtListener RECAP document lookup returned non-object JSON.")
        warnings = []
        if not payload.get("filepath_local") and not payload.get("filepath_ia"):
            warnings.append(CourtListenerWarning("recap_document_unavailable", "CourtListener has metadata but no accessible RECAP document file in this response.").to_dict())
        return {"recap_document": payload, "warnings": warnings, "source_type": "recap_document"}

    def recap_search(self, query: str, *, page_size: int = 5, documents_only: bool = False, timeout: int = 30) -> dict[str, Any]:
        return self.search(query, search_type="rd" if documents_only else "r", page_size=page_size, timeout=timeout)

    def docket_search(self, query: str, *, page_size: int = 5, timeout: int = 30) -> dict[str, Any]:
        return self.search(query, search_type="d", page_size=page_size, timeout=timeout)

    def _normalize_result(self, item: Dict[str, Any], search_type: str) -> Dict[str, Any]:
        opinions = item.get("opinions") or []
        snippets = [strip_markup(op.get("snippet", "")) for op in opinions if op.get("snippet")]
        snippets = [snippet for snippet in snippets if snippet]
        snippet = snippets[0] if snippets else strip_markup(item.get("snippet", ""))
        title = item.get("caseNameFull") or item.get("caseName") or item.get("docketNumber") or item.get("description") or "CourtListener Result"
        citations = item.get("citation") or []
        absolute_url = item.get("absolute_url") or item.get("absolute_url_exact")
        recap_documents = item.get("recap_documents") or item.get("recapDocuments") or []
        warnings = []
        if search_type in {"r", "rd", "d"}:
            if item.get("more_docs"):
                warnings.append(CourtListenerWarning("partial_recap_documents", "More RECAP documents may exist than were included in this result.").to_dict())
            if search_type in {"r", "rd"} and not recap_documents and not item.get("filepath_local") and not item.get("filepath_ia"):
                warnings.append(CourtListenerWarning("no_recap_document", "No RECAP document file was included in this result.").to_dict())
        return {
            "title": title,
            "absolute_url": absolute_url,
            "court": item.get("court"),
            "court_id": item.get("court_id"),
            "date_filed": item.get("dateFiled") or item.get("date_filed"),
            "docket_number": item.get("docketNumber") or item.get("docket_number"),
            "docket_id": item.get("docket_id") or item.get("docket"),
            "cluster_id": item.get("cluster_id"),
            "recap_document_id": item.get("recap_document_id") or item.get("id"),
            "citations": citations,
            "snippet": snippet,
            "opinions": opinions,
            "recap_documents": recap_documents,
            "result_type": search_type,
            "score": ((item.get("meta") or {}).get("score") or {}).get("bm25"),
            "source_url": f"https://www.courtlistener.com{absolute_url}" if absolute_url else None,
            "source_ids": self._source_ids(item, search_type),
            "warnings": warnings,
            "raw": item,
        }

    def _source_ids(self, item: dict[str, Any], search_type: str) -> dict[str, Any]:
        return {
            "courtlistener_type": search_type,
            "docket_id": item.get("docket_id") or item.get("docket"),
            "cluster_id": item.get("cluster_id"),
            "recap_document_id": item.get("recap_document_id") or item.get("id"),
            "absolute_url": item.get("absolute_url") or item.get("absolute_url_exact"),
        }

    def _search_warnings(self, payload: dict[str, Any], search_type: str, results: list[dict[str, Any]]) -> list[CourtListenerWarning]:
        warnings: list[CourtListenerWarning] = []
        if not results:
            warnings.append(CourtListenerWarning("no_results", "CourtListener returned no matching public results."))
        if search_type == "r" and payload.get("document_count") is not None:
            warnings.append(CourtListenerWarning("recap_count_note", "RECAP docket search may include partial docket/document coverage."))
        return warnings

    def _docket_warnings(self, docket: dict[str, Any]) -> list[dict[str, str]]:
        warnings = []
        if not docket.get("date_modified") and not docket.get("date_last_filing"):
            warnings.append(CourtListenerWarning("docket_freshness_unknown", "CourtListener did not provide enough freshness metadata to verify docket currency.").to_dict())
        if not docket.get("source"):
            warnings.append(CourtListenerWarning("docket_source_unknown", "CourtListener docket source metadata is incomplete. Verify against official court records if needed.").to_dict())
        return warnings

    def build_ingest_records(self, payload: Dict[str, Any]) -> list[Dict[str, Any]]:
        query = payload.get("query", "")
        records: list[Dict[str, Any]] = []
        for item in payload.get("results") or []:
            lines = [
                f"CourtListener result for query: {query}",
                f"Source class: {source_class_for_search_type(item.get('result_type'))}",
                f"Title: {item.get('title') or 'Unknown'}",
                f"Court: {item.get('court') or 'Unknown'}",
                f"Filed: {item.get('date_filed') or 'Unknown'}",
                f"Docket Number: {item.get('docket_number') or 'Unknown'}",
            ]
            if item.get("citations"):
                lines.append("Citations: " + ", ".join(str(cite) for cite in item.get("citations") or []))
            if item.get("source_url"):
                lines.append(f"Source URL: {item.get('source_url')}")
            if item.get("source_ids"):
                lines.append(f"Source IDs: {item.get('source_ids')}")
            if item.get("snippet"):
                lines.append("")
                lines.append("Snippet:")
                lines.append(item["snippet"])
            records.append(
                {
                    "title": item.get("title") or "CourtListener Result",
                    "text": "\n".join(lines).strip(),
                    "metadata": {
                        "provider": "courtlistener",
                        "query": query,
                        "source_class": source_class_for_search_type(item.get("result_type")),
                        "court": item.get("court"),
                        "court_id": item.get("court_id"),
                        "date_filed": item.get("date_filed"),
                        "docket_number": item.get("docket_number"),
                        "docket_id": item.get("docket_id"),
                        "cluster_id": item.get("cluster_id"),
                        "recap_document_id": item.get("recap_document_id"),
                        "citations": item.get("citations") or [],
                        "source_url": item.get("source_url"),
                        "source_ids": item.get("source_ids") or {},
                        "warnings": item.get("warnings") or [],
                        "result_type": item.get("result_type"),
                    },
                }
            )
        return records


def source_class_for_search_type(search_type: str | None) -> str:
    if search_type == "o":
        return "courtlistener_public_case_law"
    if search_type == "d":
        return "courtlistener_public_docket_metadata"
    if search_type in {"r", "rd"}:
        return "recap_docket_or_document_data"
    return "courtlistener_public_legal_material"
