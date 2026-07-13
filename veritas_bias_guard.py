from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BiasGuardResult:
    approved: bool
    issues: list[str] = field(default_factory=list)
    guidance: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"approved": self.approved, "issues": self.issues, "guidance": self.guidance}


PROTECTED_CLASS_TERMS = [
    "race",
    "religion",
    "disability",
    "disabled",
    "nationality",
    "immigrant",
    "gender",
    "pregnant",
    "age",
]

ONE_SIDED_TERMS = [
    "obviously lying",
    "clearly guilty",
    "definitely liable",
    "guaranteed win",
    "we will win",
    "they always",
    "never believable",
]


def evaluate_bias_and_safety(text: str, *, has_sources: bool = False) -> BiasGuardResult:
    lowered = str(text or "").lower()
    issues: list[str] = []
    guidance: list[str] = []

    if any(term in lowered for term in PROTECTED_CLASS_TERMS) and any(
        marker in lowered for marker in ["because", "therefore", "so they", "means they"]
    ):
        issues.append("protected_class_inference_risk")
        guidance.append("Do not infer credibility, liability, or intent from protected traits.")

    if any(term in lowered for term in ONE_SIDED_TERMS):
        issues.append("one_sided_or_outcome_language")
        guidance.append("Frame as evidence support, disputed issues, or attorney-review questions; avoid outcome guarantees.")

    if re.search(r"\b(always|never)\b", lowered) and any(term in lowered for term in ["witness", "judge", "opposing", "client"]):
        issues.append("absolute_characterization_risk")
        guidance.append("Replace absolute characterizations with source-linked observations.")

    if not has_sources and any(term in lowered for term in ["prove", "proves", "liable", "fraud", "negligent", "breach"]):
        issues.append("unsupported_legal_conclusion_risk")
        guidance.append("Ask for or cite source material before legal characterization.")

    return BiasGuardResult(approved=not issues, issues=issues, guidance=guidance)

