from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any

import requests


DATA_SEC_ROOT = "https://data.sec.gov"
EFTS_ROOT = "https://efts.sec.gov/LATEST"
DEFAULT_USER_AGENT = "CLAIRE Veritas EDGAR Collector/1.0 steve@clairesystems.ai"


class EdgarRateLimitError(RuntimeError):
    def __init__(self, message: str, *, wait_seconds: float | None = None):
        super().__init__(message)
        self.wait_seconds = wait_seconds


@dataclass
class EdgarWarning:
    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def accession_nodashes(accession: str) -> str:
    return "".join(ch for ch in str(accession or "") if ch.isdigit())


def normalize_cik(cik: str | int) -> str:
    raw = "".join(ch for ch in str(cik or "") if ch.isdigit())
    if not raw:
        raise ValueError("CIK is required")
    return raw.zfill(10)


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


class EdgarClient:
    def __init__(
        self,
        *,
        user_agent: str | None = None,
        data_root: str = DATA_SEC_ROOT,
        efts_root: str = EFTS_ROOT,
        session: Any | None = None,
        min_interval_seconds: float = 0.25,
        max_retries: int = 2,
        max_backoff_seconds: float = 8.0,
    ) -> None:
        self.user_agent = (
            user_agent
            or os.getenv("VERITAS_EDGAR_USER_AGENT")
            or os.getenv("SEC_EDGAR_USER_AGENT")
            or DEFAULT_USER_AGENT
        ).strip()
        self.data_root = data_root.rstrip("/")
        self.efts_root = efts_root.rstrip("/")
        self.session = session or requests.Session()
        self.min_interval_seconds = max(0.0, float(min_interval_seconds))
        self.max_retries = max(0, int(max_retries))
        self.max_backoff_seconds = max(0.0, float(max_backoff_seconds))
        self._last_request_at = 0.0

    def configured(self) -> bool:
        return bool(self.user_agent)

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
        }

    def _sleep_for_client_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval_seconds:
            time.sleep(self.min_interval_seconds - elapsed)
        self._last_request_at = time.monotonic()

    def _request(
        self,
        method: str,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        timeout: int = 30,
    ) -> dict[str, Any]:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            self._sleep_for_client_rate_limit()
            response = self.session.request(
                method.upper(),
                url,
                headers=self._headers(),
                params=params,
                json=json_body,
                timeout=max(1, int(timeout or 30)),
            )
            if response.status_code == 429:
                wait_seconds = _retry_after_seconds(response.headers.get("Retry-After"))
                if attempt < self.max_retries:
                    time.sleep(min(wait_seconds or (2**attempt), self.max_backoff_seconds))
                    continue
                raise EdgarRateLimitError("SEC EDGAR rate limit reached.", wait_seconds=wait_seconds)
            try:
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries and response.status_code in {500, 502, 503, 504}:
                    time.sleep(min(2**attempt, self.max_backoff_seconds))
                    continue
                raise
            if not isinstance(payload, dict):
                raise RuntimeError("SEC EDGAR returned non-object JSON.")
            return payload
        raise RuntimeError(f"SEC EDGAR request failed: {last_exc}")

    def company_submissions(self, cik: str | int, *, timeout: int = 30) -> dict[str, Any]:
        normalized_cik = normalize_cik(cik)
        payload = self._request("GET", f"{self.data_root}/submissions/CIK{normalized_cik}.json", timeout=timeout)
        return {
            "ok": True,
            "source": "SEC EDGAR data.sec.gov submissions",
            "query": normalized_cik,
            "cik": normalized_cik,
            "company": payload.get("name") or payload.get("entityName"),
            "tickers": payload.get("tickers") or [],
            "exchanges": payload.get("exchanges") or [],
            "filings": self._normalize_recent_filings(payload),
            "warnings": self._submissions_warnings(payload),
            "retrieved_at": time.time(),
        }

    def search(self, query: str, *, page_size: int = 10, start: int = 0, timeout: int = 30) -> dict[str, Any]:
        body = {
            "q": query,
            "from": max(0, int(start or 0)),
            "size": max(1, min(int(page_size or 10), 50)),
        }
        payload = self._request("POST", f"{self.efts_root}/search-index", json_body=body, timeout=timeout)
        results = self._normalize_search_results(payload, query=query)
        return {
            "ok": True,
            "source": "SEC EDGAR efts.sec.gov full-text search",
            "query": query,
            "page_size": body["size"],
            "start": body["from"],
            "count": payload.get("hits", {}).get("total", {}).get("value") if isinstance(payload.get("hits"), dict) else payload.get("total"),
            "results": results,
            "warnings": self._search_warnings(payload, results),
            "retrieved_at": time.time(),
        }

    def _normalize_recent_filings(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        recent = ((payload.get("filings") or {}).get("recent") or {})
        accessions = recent.get("accessionNumber") or []
        rows: list[dict[str, Any]] = []
        for index, accession in enumerate(accessions):
            cik = normalize_cik(payload.get("cik") or payload.get("CIK") or "")
            primary_document = _list_get(recent.get("primaryDocument"), index)
            filing = {
                "company": payload.get("name") or payload.get("entityName"),
                "cik": cik,
                "accession_number": accession,
                "form": _list_get(recent.get("form"), index),
                "filing_date": _list_get(recent.get("filingDate"), index),
                "report_date": _list_get(recent.get("reportDate"), index),
                "primary_document": primary_document,
                "source_url": self._filing_url(cik, accession, primary_document),
            }
            filing["content_hash"] = _content_hash(filing)
            filing["source_ids"] = {
                "cik": cik,
                "accession_number": accession,
                "accession_nodashes": accession_nodashes(accession),
            }
            rows.append(filing)
        return rows

    def _normalize_search_results(self, payload: dict[str, Any], *, query: str) -> list[dict[str, Any]]:
        raw_hits: list[Any]
        hits = payload.get("hits")
        if isinstance(hits, dict):
            raw_hits = hits.get("hits") or []
        else:
            raw_hits = payload.get("results") or payload.get("filings") or []
        results: list[dict[str, Any]] = []
        for raw in raw_hits:
            item = raw.get("_source") if isinstance(raw, dict) and isinstance(raw.get("_source"), dict) else raw
            if not isinstance(item, dict):
                continue
            cik = str(item.get("cik") or item.get("ciks") or item.get("cik_display") or "")
            if isinstance(item.get("ciks"), list) and item.get("ciks"):
                cik = str(item["ciks"][0])
            accession = str(item.get("adsh") or item.get("accession_number") or item.get("accessionNo") or item.get("accessionNumber") or "")
            primary_document = str(item.get("file") or item.get("primaryDocument") or item.get("document") or "")
            normalized_cik = normalize_cik(cik) if "".join(ch for ch in cik if ch.isdigit()) else ""
            result = {
                "title": item.get("display_names") or item.get("entity") or item.get("companyName") or item.get("company") or "SEC EDGAR filing",
                "query": query,
                "company": item.get("entity") or item.get("companyName") or item.get("company"),
                "cik": normalized_cik,
                "accession_number": accession,
                "form": item.get("form") or item.get("formType"),
                "filing_date": item.get("file_date") or item.get("filingDate") or item.get("filedAt"),
                "primary_document": primary_document,
                "snippet": item.get("summary") or item.get("text") or item.get("snippet") or "",
                "source_url": self._filing_url(normalized_cik, accession, primary_document) if normalized_cik and accession else item.get("linkToFilingDetails"),
            }
            result["content_hash"] = _content_hash(result)
            result["source_ids"] = {
                "cik": normalized_cik,
                "accession_number": accession,
                "accession_nodashes": accession_nodashes(accession),
            }
            results.append(result)
        return results

    def _filing_url(self, cik: str, accession: str, primary_document: str | None) -> str:
        if not cik or not accession:
            return ""
        path_cik = str(int(cik))
        accession_path = accession_nodashes(accession)
        if primary_document:
            return f"https://www.sec.gov/Archives/edgar/data/{path_cik}/{accession_path}/{primary_document}"
        return f"https://www.sec.gov/Archives/edgar/data/{path_cik}/{accession_path}/"

    def _submissions_warnings(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        warnings: list[EdgarWarning] = []
        if not ((payload.get("filings") or {}).get("recent") or {}).get("accessionNumber"):
            warnings.append(EdgarWarning("no_recent_filings", "SEC EDGAR returned no recent filings in this submissions response."))
        return [warning.to_dict() for warning in warnings]

    def _search_warnings(self, payload: dict[str, Any], results: list[dict[str, Any]]) -> list[dict[str, str]]:
        warnings: list[EdgarWarning] = [
            EdgarWarning("sec_public_source", "SEC EDGAR material is external public company/filing data and must be attached or admitted before matter use.")
        ]
        if not results:
            warnings.append(EdgarWarning("no_results", "SEC EDGAR returned no matching full-text search results."))
        return [warning.to_dict() for warning in warnings]

    def build_ingest_records(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for item in payload.get("results") or payload.get("filings") or []:
            lines = [
                f"SEC EDGAR result for query: {payload.get('query') or item.get('cik') or ''}",
                f"Company: {item.get('company') or item.get('title') or 'Unknown'}",
                f"CIK: {item.get('cik') or 'Unknown'}",
                f"Accession Number: {item.get('accession_number') or 'Unknown'}",
                f"Form: {item.get('form') or 'Unknown'}",
                f"Filing Date: {item.get('filing_date') or 'Unknown'}",
            ]
            if item.get("source_url"):
                lines.append(f"Source URL: {item.get('source_url')}")
            if item.get("snippet"):
                lines.extend(["", "Snippet:", str(item.get("snippet"))])
            records.append(
                {
                    "title": item.get("title") or f"SEC EDGAR {item.get('form') or 'filing'}",
                    "text": "\n".join(lines).strip(),
                    "metadata": {
                        "provider": "sec_edgar",
                        "source_class": "sec_edgar_public_filing",
                        "query": payload.get("query"),
                        "company": item.get("company") or item.get("title"),
                        "cik": item.get("cik"),
                        "accession_number": item.get("accession_number"),
                        "form": item.get("form"),
                        "filing_date": item.get("filing_date"),
                        "primary_document": item.get("primary_document"),
                        "source_url": item.get("source_url"),
                        "source_ids": item.get("source_ids") or {},
                        "content_hash": item.get("content_hash"),
                        "warnings": payload.get("warnings") or [],
                    },
                }
            )
        return records


def _list_get(values: Any, index: int) -> Any:
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]


def _content_hash(payload: dict[str, Any]) -> str:
    stable = "|".join(str(payload.get(key) or "") for key in ["cik", "accession_number", "form", "filing_date", "primary_document", "source_url"])
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()
