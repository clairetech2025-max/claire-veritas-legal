from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


SECRET_SOURCES = (
    ("courtlistener", ("COURTLISTENER_TOKEN", "COURTLISTENER_API_KEY")),
    ("constitutional", ("CONSTITUTIONAL_API_KEY",)),
)

PUBLIC_SOURCES = {
    "public_web": {
        "configured": True,
        "key_name": None,
        "official": False,
        "base_urls": ["https://html.duckduckgo.com/html/"],
        "note": "General public web research is available for source discovery. Verify primary sources before legal reliance.",
    },
    "california_regulations": {
        "configured": True,
        "key_name": None,
        "official": False,
        "base_urls": ["https://regulations.justia.com/states/california", "https://govt.westlaw.com/calregs/Index"],
        "note": "Justia public regulation pages are used for lookup; verify against the official California Code of Regulations source before reliance.",
    },
    "sec_edgar": {
        "configured": True,
        "key_name": None,
        "official": True,
        "base_urls": ["https://data.sec.gov", "https://efts.sec.gov/LATEST/search-index"],
    }
}


def load_local_env(project_root: Path) -> None:
    for candidate in (project_root / ".env.local", project_root / ".env"):
        if not candidate.exists():
            continue
        for raw_line in candidate.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def external_source_status() -> Dict[str, Dict[str, object]]:
    sources: Dict[str, Dict[str, object]] = {}
    for provider, keys in SECRET_SOURCES:
        configured_key = next((key for key in keys if os.getenv(key, "").strip()), keys[0])
        value = os.getenv(configured_key, "").strip()
        sources[provider] = {
            "configured": bool(value),
            "key_name": configured_key,
        }
    sources.update(PUBLIC_SOURCES)
    return sources
