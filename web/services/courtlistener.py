from __future__ import annotations

import html
import os
import re
from typing import Any, Dict, List, Optional

import requests


API_ROOT = "https://www.courtlistener.com/api/rest/v4"


def _strip_markup(text: str) -> str:
    return re.sub(r"<[^>]+>", "", html.unescape(text or "")).strip()


class CourtListenerClient:
    def __init__(self, api_key: Optional[str] = None, api_root: str = API_ROOT):
        self.api_key = (api_key or os.getenv("COURTLISTENER_API_KEY") or "").strip()
        self.api_root = api_root.rstrip("/")

    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> Dict[str, str]:
        if not self.configured():
            raise RuntimeError("COURTLISTENER_API_KEY is not configured.")
        return {"Authorization": f"Token {self.api_key}"}

    def search(self, query: str, *, search_type: str = "r", page_size: int = 5, semantic: bool = False) -> Dict[str, Any]:
        params = {
            "q": query,
            "type": search_type or "r",
            "page_size": max(1, min(int(page_size or 5), 20)),
        }
        if semantic:
            params["semantic"] = "true"
        response = requests.get(f"{self.api_root}/search/", headers=self._headers(), params=params, timeout=30)
        response.raise_for_status()
        payload = response.json()
        results = [self._normalize_result(item, params["type"]) for item in payload.get("results") or []]
        results = results[: params["page_size"]]
        return {
            "query": query,
            "search_type": params["type"],
            "page_size": params["page_size"],
            "semantic": semantic,
            "count": payload.get("count", len(results)),
            "results": results,
            "next": payload.get("next"),
            "previous": payload.get("previous"),
        }

    def _normalize_result(self, item: Dict[str, Any], search_type: str) -> Dict[str, Any]:
        opinions = item.get("opinions") or []
        snippets = [_strip_markup(op.get("snippet", "")) for op in opinions if op.get("snippet")]
        snippets = [snippet for snippet in snippets if snippet]
        snippet = snippets[0] if snippets else _strip_markup(item.get("snippet", ""))
        title = item.get("caseNameFull") or item.get("caseName") or item.get("docketNumber") or "CourtListener Result"
        citations = item.get("citation") or []
        return {
            "title": title,
            "absolute_url": item.get("absolute_url"),
            "court": item.get("court"),
            "court_id": item.get("court_id"),
            "date_filed": item.get("dateFiled"),
            "docket_number": item.get("docketNumber"),
            "docket_id": item.get("docket_id"),
            "cluster_id": item.get("cluster_id"),
            "citations": citations,
            "snippet": snippet,
            "opinions": opinions,
            "result_type": search_type,
            "score": ((item.get("meta") or {}).get("score") or {}).get("bm25"),
            "source_url": f"https://www.courtlistener.com{item.get('absolute_url')}" if item.get("absolute_url") else None,
            "raw": item,
        }

    def build_ingest_records(self, payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        query = payload.get("query", "")
        records: List[Dict[str, Any]] = []
        for item in payload.get("results") or []:
            lines = [
                f"CourtListener result for query: {query}",
                f"Title: {item.get('title') or 'Unknown'}",
                f"Court: {item.get('court') or 'Unknown'}",
                f"Filed: {item.get('date_filed') or 'Unknown'}",
                f"Docket Number: {item.get('docket_number') or 'Unknown'}",
            ]
            if item.get("citations"):
                lines.append("Citations: " + ", ".join(str(cite) for cite in item.get("citations") or []))
            if item.get("source_url"):
                lines.append(f"Source URL: {item.get('source_url')}")
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
                        "court": item.get("court"),
                        "court_id": item.get("court_id"),
                        "date_filed": item.get("date_filed"),
                        "docket_number": item.get("docket_number"),
                        "docket_id": item.get("docket_id"),
                        "cluster_id": item.get("cluster_id"),
                        "citations": item.get("citations") or [],
                        "source_url": item.get("source_url"),
                        "result_type": item.get("result_type"),
                    },
                }
            )
        return records
