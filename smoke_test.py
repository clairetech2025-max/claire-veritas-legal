#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from web.services.workspace import WorkspaceStore


ROOT = Path(__file__).resolve().parent


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def check_public_files() -> None:
    required = [
        "README.md",
        "SELLABLE_PACKAGE.md",
        "requirements-web.txt",
        "web/app.py",
        "web/index.html",
        "web/static/app.js",
        "web/static/styles.css",
        "demo_seed.py",
    ]
    for relpath in required:
        assert_true((ROOT / relpath).exists(), f"missing {relpath}")


def check_ignored_private_paths() -> None:
    ignored = subprocess.run(
        ["git", "check-ignore", "memory/", "vault/", ".claire_veritas/", ".env.local"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = set(ignored.stdout.splitlines())
    for relpath in {"memory/", "vault/", ".claire_veritas/", ".env.local"}:
        assert_true(relpath in output, f"{relpath} is not ignored")


def check_workspace_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "web" / "rules").mkdir(parents=True)
        for profile in (ROOT / "web" / "rules").glob("*.json"):
            (root / "web" / "rules" / profile.name).write_text(profile.read_text(encoding="utf-8"), encoding="utf-8")
        store = WorkspaceStore(root)
        matter = store.upsert_matter(
            {
                "case_id": "smoke-demo",
                "title": "Smoke Demo Matter",
                "court_profile_id": "federal_district_civil",
                "confidentiality_level": "Synthetic",
                "notes": "Synthetic smoke test matter.",
            }
        )
        result = store.ingest_text(
            "Exhibit A. The service notice identifies an elevator outage and alternate routing.",
            case_id="smoke-demo",
            case_title=matter["title"],
            source_type="demo_exhibit",
            file_name="exhibit-a.txt",
            mime_type="text/plain",
            metadata={"synthetic": True},
        )
        hits = store.search("elevator outage alternate routing", case_id="smoke-demo", top_k=3)
        assert_true(result.get("chunks", 0) >= 1, "ingest wrote no chunks")
        assert_true(bool(hits), "search returned no hits")
        assert_true(hits[0].get("case_id") == "smoke-demo", "search hit case mismatch")


def main() -> int:
    check_public_files()
    check_ignored_private_paths()
    check_workspace_roundtrip()
    print("smoke_test: all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
