from __future__ import annotations

from typing import Dict, Optional

from correction_learning import matching_corrections
from correction_store import CorrectionStore


def classify_lane(prompt: str, *, store: Optional[CorrectionStore] = None) -> Dict[str, object]:
    matches = matching_corrections(prompt, store=store)
    if matches:
        lane = matches[0].get("lane_override_if_any") or "CORRECTION_RULE"
        return {"lane": lane, "source": "explicit_correction", "corrections": matches}

    lowered = prompt.lower()
    if "veritas legal" in lowered or ("evidence" in lowered and "attorney" in lowered):
        return {"lane": "LEGAL_INTAKE", "source": "heuristic", "corrections": []}
    if any(term in lowered for term in ("azure", "nvidia", "mlperf", "gpu", "llama 405b")):
        return {"lane": "AI_INFRASTRUCTURE", "source": "heuristic", "corrections": []}
    if "are" in lowered and ("mean" in lowered or "define" in lowered):
        return {"lane": "PROJECT_TRUTH", "source": "heuristic", "corrections": []}
    return {"lane": "LEGAL_CASE", "source": "default", "corrections": []}

