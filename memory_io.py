from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, Iterator


def _ts() -> float:
    return time.time()


def append_jsonl(path: str, record: Dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_jsonl(path: str) -> Iterator[Dict[str, Any]]:
    target = Path(path)
    if not target.exists():
        return
    with target.open("r", encoding="utf-8", errors="ignore") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except Exception:
                continue
            if isinstance(payload, dict):
                yield payload
