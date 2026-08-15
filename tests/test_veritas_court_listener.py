from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from courtlistener_client import CourtListenerClient
from memory_io import read_jsonl
from veritas_court_listener import VeritasCourtListener
from veritas_source_trace import source_trace_path


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


def test_workflow_explains_source_separation():
    with tempfile.TemporaryDirectory() as tmp:
        workflow = VeritasCourtListener(tmp, CourtListenerClient(token="", session=FakeSession([]))).workflow_explanation()
        assert "user-provided evidence" in workflow
        assert "public case law" in workflow
        assert "RECAP docket/document data" in workflow
        assert "not a substitute" in workflow


def test_missing_token_uses_public_search_and_writes_trace():
    with tempfile.TemporaryDirectory() as tmp:
        payload = {"count": 0, "results": []}
        vc = VeritasCourtListener(tmp, CourtListenerClient(token="", session=FakeSession([FakeResponse(payload=payload)]), min_interval_seconds=0))
        result = vc.search("demo", case_id="case-1")
        assert result["configured"] is False
        assert result["public_access"] is True
        assert result["warnings"][0]["code"] == "no_results"
        traces = list(read_jsonl(str(source_trace_path(Path(tmp)))))
        assert traces[-1]["case_id"] == "case-1"


def test_search_writes_source_traces_with_ids():
    payload = {
        "count": 1,
        "results": [
            {
                "caseName": "Demo v. Example",
                "cluster_id": 99,
                "citation": ["1 F.4th 2"],
                "absolute_url": "/opinion/99/demo/",
            }
        ],
    }
    with tempfile.TemporaryDirectory() as tmp:
        client = CourtListenerClient(token="tok", session=FakeSession([FakeResponse(payload=payload)]), min_interval_seconds=0)
        vc = VeritasCourtListener(tmp, client)
        result = vc.search("demo", search_type="o", case_id="case-1")
        assert result["source_class"] == "courtlistener_public_case_law"
        assert result["traces"][0]["source_ids"]["cluster_id"] == 99
        assert result["traces"][0]["source_url"].endswith("/opinion/99/demo/")


def test_citation_lookup_writes_trace_and_warnings():
    payload = [{"citation": "1 U.S. 200", "status": 404, "clusters": [], "error_message": "Citation not found"}]
    with tempfile.TemporaryDirectory() as tmp:
        client = CourtListenerClient(token="tok", session=FakeSession([FakeResponse(payload=payload)]), min_interval_seconds=0)
        vc = VeritasCourtListener(tmp, client)
        result = vc.citation_lookup(volume="1", reporter="U.S.", page="200", case_id="case-1")
        assert result["warnings"][0]["code"] == "citation_not_found"
        assert result["trace"]["source_class"] == "courtlistener_public_case_law"


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
    print("test_veritas_court_listener: all checks passed")
