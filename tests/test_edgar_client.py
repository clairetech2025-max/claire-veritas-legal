from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edgar_client import DEFAULT_USER_AGENT, EdgarClient, EdgarRateLimitError, normalize_cik


class FakeResponse:
    def __init__(self, status_code=200, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append({"method": method, "url": url, **kwargs})
        return self.responses.pop(0)


def test_normalize_cik_pads_to_ten_digits():
    assert normalize_cik("320193") == "0000320193"


def test_company_submissions_normalizes_recent_filings_and_user_agent():
    payload = {
        "cik": "320193",
        "name": "Apple Inc.",
        "tickers": ["AAPL"],
        "filings": {
            "recent": {
                "accessionNumber": ["0000320193-24-000123"],
                "form": ["10-K"],
                "filingDate": ["2024-11-01"],
                "reportDate": ["2024-09-28"],
                "primaryDocument": ["aapl-20240928.htm"],
            }
        },
    }
    session = FakeSession([FakeResponse(payload=payload)])
    client = EdgarClient(session=session, min_interval_seconds=0)

    result = client.company_submissions("320193")

    assert result["cik"] == "0000320193"
    assert result["filings"][0]["accession_number"] == "0000320193-24-000123"
    assert result["filings"][0]["source_ids"]["accession_nodashes"] == "000032019324000123"
    assert result["filings"][0]["source_url"].endswith("/aapl-20240928.htm")
    assert result["filings"][0]["content_hash"]
    assert session.calls[0]["headers"]["User-Agent"] == DEFAULT_USER_AGENT
    assert "data.sec.gov/submissions/CIK0000320193.json" in session.calls[0]["url"]


def test_edgar_full_text_search_posts_to_efts_and_normalizes_hits():
    payload = {
        "hits": {
            "total": {"value": 1},
            "hits": [
                {
                    "_source": {
                        "entity": "Apple Inc.",
                        "ciks": ["320193"],
                        "adsh": "0000320193-24-000123",
                        "form": "10-K",
                        "file_date": "2024-11-01",
                        "file": "aapl-20240928.htm",
                        "summary": "annual report text",
                    }
                }
            ],
        }
    }
    session = FakeSession([FakeResponse(payload=payload)])
    client = EdgarClient(session=session, min_interval_seconds=0)

    result = client.search("Apple artificial intelligence", page_size=2)

    assert result["results"][0]["company"] == "Apple Inc."
    assert result["results"][0]["cik"] == "0000320193"
    assert result["results"][0]["form"] == "10-K"
    assert result["results"][0]["content_hash"]
    assert session.calls[0]["method"] == "POST"
    assert "efts.sec.gov/LATEST/search-index" in session.calls[0]["url"]
    assert session.calls[0]["json"]["q"] == "Apple artificial intelligence"


def test_edgar_rate_limit_raises_with_wait_seconds():
    session = FakeSession([FakeResponse(status_code=429, payload={"detail": "limited"}, headers={"Retry-After": "4"})])
    client = EdgarClient(session=session, min_interval_seconds=0, max_retries=0)
    try:
        client.search("foo")
    except EdgarRateLimitError as exc:
        assert exc.wait_seconds == 4
    else:
        raise AssertionError("rate limit did not raise")


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
    print("test_edgar_client: all checks passed")
