from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from courtlistener_client import CourtListenerClient, CourtListenerRateLimitError


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


def test_token_header_uses_courtlistener_token():
    session = FakeSession([FakeResponse(payload={"count": 0, "results": []})])
    client = CourtListenerClient(token="tok-test", session=session, min_interval_seconds=0)
    result = client.search("foo")
    assert result["warnings"][0]["code"] == "no_results"
    assert session.calls[0]["headers"]["Authorization"] == "Token tok-test"


def test_missing_token_uses_public_request_without_auth_header():
    session = FakeSession([FakeResponse(payload={"count": 0, "results": []})])
    client = CourtListenerClient(token="", session=session, min_interval_seconds=0)
    assert not client.configured()
    result = client.search("foo")
    assert result["authenticated"] is False
    assert "Authorization" not in session.calls[0]["headers"]
    assert session.calls[0]["headers"]["Accept"] == "application/json"


def test_rate_limit_raises_with_wait_seconds():
    session = FakeSession([FakeResponse(status_code=429, payload={"detail": "limited"}, headers={"Retry-After": "3"})])
    client = CourtListenerClient(token="tok-test", session=session, min_interval_seconds=0, max_retries=0)
    try:
        client.search("foo")
    except CourtListenerRateLimitError as exc:
        assert exc.wait_seconds == 3
    else:
        raise AssertionError("rate limit did not raise")


def test_search_normalizes_recap_warnings():
    payload = {
        "count": 1,
        "document_count": 4,
        "results": [{"caseName": "Demo", "docket_id": 123, "more_docs": True, "absolute_url": "/docket/123/demo/"}],
    }
    client = CourtListenerClient(token="tok-test", session=FakeSession([FakeResponse(payload=payload)]), min_interval_seconds=0)
    result = client.search("demo", search_type="r")
    assert result["results"][0]["warnings"][0]["code"] == "partial_recap_documents"
    assert result["results"][0]["source_ids"]["docket_id"] == 123


def test_citation_lookup_posts_text():
    session = FakeSession([FakeResponse(payload=[{"citation": "576 U.S. 644", "status": 200, "clusters": []}])])
    client = CourtListenerClient(token="tok-test", session=session, min_interval_seconds=0)
    result = client.citation_lookup(text="Obergefell, 576 U.S. 644")
    assert result["results"][0]["citation"] == "576 U.S. 644"
    assert session.calls[0]["method"] == "POST"
    assert session.calls[0]["data"]["text"] == "Obergefell, 576 U.S. 644"


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
    print("test_courtlistener_client: all checks passed")
