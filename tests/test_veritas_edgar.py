from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from edgar_client import EdgarClient
from memory_io import read_jsonl
from veritas_edgar import VeritasEdgar
from veritas_source_trace import source_trace_path
from fastapi.testclient import TestClient


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


def test_edgar_workflow_explains_source_separation():
    with tempfile.TemporaryDirectory() as tmp:
        workflow = VeritasEdgar(tmp).workflow_explanation()
        assert "official SEC" in workflow
        assert "separate from user evidence" in workflow
        assert "CIK" in workflow


def test_edgar_search_writes_source_trace_with_accession_id():
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
                    }
                }
            ],
        }
    }
    with tempfile.TemporaryDirectory() as tmp:
        client = EdgarClient(session=FakeSession([FakeResponse(payload=payload)]), min_interval_seconds=0)
        workflow = VeritasEdgar(tmp, client)

        result = workflow.search("Apple 10-K", case_id="case-1")

        assert result["source_class"] == "sec_edgar_public_filing"
        assert result["results"][0]["source_ids"]["accession_number"] == "0000320193-24-000123"
        traces = list(read_jsonl(str(source_trace_path(Path(tmp)))))
        assert traces[-1]["source_class"] == "sec_edgar_public_filing"
        assert traces[-1]["case_id"] == "case-1"
        assert traces[-1]["source_ids"]["cik"] == "0000320193"


def test_edgar_search_api_route_returns_normalized_public_filing(monkeypatch):
    import web.app as app_module

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
                    }
                }
            ],
        }
    }
    with tempfile.TemporaryDirectory() as tmp:
        edgar = VeritasEdgar(tmp, EdgarClient(session=FakeSession([FakeResponse(payload=payload)]), min_interval_seconds=0))
        monkeypatch.setattr(app_module, "VERITAS_EDGAR", edgar)
        client = TestClient(app_module.app)

        response = client.post("/edgar/search", json={"query": "Apple 10-K", "case_id": "case-1", "page_size": 1})

        assert response.status_code == 200
        body = response.json()
        assert body["results"][0]["cik"] == "0000320193"
        assert body["results"][0]["accession_number"] == "0000320193-24-000123"
        assert body["warnings"][0]["code"] == "sec_public_source"


if __name__ == "__main__":
    for name, value in sorted(globals().items()):
        if name.startswith("test_") and callable(value):
            value()
    print("test_veritas_edgar: all checks passed")
