from __future__ import annotations

from pathlib import Path
from typing import Any

from edgar_client import EdgarClient, EdgarRateLimitError
from veritas_source_trace import build_source_trace, write_source_trace


class VeritasEdgar:
    def __init__(self, root: str | Path, client: EdgarClient | None = None):
        self.root = Path(root)
        self.client = client or EdgarClient()

    def configured(self) -> bool:
        return self.client.configured()

    def workflow_explanation(self) -> str:
        return (
            "SEC EDGAR workflow: I can search official SEC full-text filing data and retrieve company submissions from data.sec.gov. "
            "I keep EDGAR public company/filing material separate from user evidence until a user explicitly attaches or imports it into a matter. "
            "Each result carries CIK, accession number, filing URL, content hash, retrieval metadata, and warnings where coverage is partial."
        )

    def search(self, query: str, *, page_size: int = 10, start: int = 0, case_id: str | None = None) -> dict[str, Any]:
        try:
            payload = self.client.search(query, page_size=page_size, start=start)
        except EdgarRateLimitError as exc:
            return self._rate_limited("edgar_search", query, case_id, exc)
        payload["workflow"] = self.workflow_explanation()
        payload["source_class"] = "sec_edgar_public_filing"
        payload["configured"] = self.configured()
        payload["traces"] = self._trace_results(payload, action="edgar_search", case_id=case_id)
        return payload

    def company_submissions(self, cik: str, *, case_id: str | None = None) -> dict[str, Any]:
        try:
            payload = self.client.company_submissions(cik)
        except EdgarRateLimitError as exc:
            return self._rate_limited("edgar_company_submissions", str(cik), case_id, exc)
        payload["workflow"] = self.workflow_explanation()
        payload["source_class"] = "sec_edgar_public_filing"
        payload["configured"] = self.configured()
        payload["traces"] = self._trace_results(payload, action="edgar_company_submissions", case_id=case_id)
        return payload

    def _trace_results(self, payload: dict[str, Any], *, action: str, case_id: str | None) -> list[dict[str, Any]]:
        traces = []
        rows = payload.get("results") or payload.get("filings") or []
        warnings = list(payload.get("warnings") or [])
        if len(rows) > 25:
            warnings.append(
                {
                    "code": "trace_limit_applied",
                    "message": "SEC EDGAR response contained more than 25 rows; source traces were capped while response rows remained available.",
                }
            )
        for item in rows[:25]:
            trace = build_source_trace(
                source_class="sec_edgar_public_filing",
                action=action,
                query=payload.get("query") or "",
                source_url=item.get("source_url"),
                source_ids=item.get("source_ids") or {},
                warnings=warnings,
                case_id=case_id,
            )
            traces.append(write_source_trace(self.root, trace))
        if not traces:
            trace = build_source_trace(
                source_class="sec_edgar_public_filing",
                action=action,
                query=payload.get("query") or "",
                warnings=payload.get("warnings") or [],
                case_id=case_id,
            )
            traces.append(write_source_trace(self.root, trace))
        return traces

    def _rate_limited(self, action: str, query: str, case_id: str | None, exc: EdgarRateLimitError) -> dict[str, Any]:
        warning = {
            "code": "sec_edgar_rate_limited",
            "message": "SEC EDGAR rate limit reached; wait before retrying.",
            "wait_seconds": exc.wait_seconds,
        }
        trace = build_source_trace(
            source_class="sec_edgar_public_filing",
            action=action,
            query=query,
            warnings=[warning],
            case_id=case_id,
        )
        return {
            "configured": self.configured(),
            "ok": False,
            "query": query,
            "results": [],
            "warnings": [warning],
            "workflow": self.workflow_explanation(),
            "trace": write_source_trace(self.root, trace),
        }
