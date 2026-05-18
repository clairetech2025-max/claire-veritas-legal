from __future__ import annotations

import os
from pathlib import Path
from typing import Dict


SECRET_KEYS = (
    "COURTLISTENER_API_KEY",
    "CONSTITUTIONAL_API_KEY",
)


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
    for key in SECRET_KEYS:
        provider = key.replace("_API_KEY", "").lower()
        value = os.getenv(key, "").strip()
        sources[provider] = {
            "configured": bool(value),
            "key_name": key,
        }
    return sources
