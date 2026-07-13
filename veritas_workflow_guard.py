from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowGuardResult:
    allowed: bool
    action: str
    severity: str = "normal"
    reasons: list[str] = field(default_factory=list)
    explanation: str = ""
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "action": self.action,
            "severity": self.severity,
            "reasons": self.reasons,
            "explanation": self.explanation,
            "requires_confirmation": self.requires_confirmation,
        }


def evaluate_workflow_request(text: str) -> WorkflowGuardResult:
    lowered = str(text or "").lower()

    if any(marker in lowered for marker in ["delete all", "wipe", "erase", "purge", "remove all evidence"]):
        return WorkflowGuardResult(
            allowed=False,
            action="destructive_evidence_change",
            severity="blocked",
            reasons=["destructive evidence changes can corrupt the matter record"],
            explanation="I cannot perform destructive evidence changes from chat. Preserve the record and create an audit-backed removal workflow if cleanup is needed.",
        )

    if any(marker in lowered for marker in ["file this", "submit to court", "e-file", "send to court"]):
        return WorkflowGuardResult(
            allowed=False,
            action="court_filing",
            severity="blocked",
            reasons=["court filing requires attorney review and external filing authority"],
            explanation="I can prepare an attorney-review packet, but I cannot file or submit documents to a court from this workspace.",
        )

    if any(marker in lowered for marker in ["tell me i will win", "guarantee we win", "final legal advice", "what is my legal outcome"]):
        return WorkflowGuardResult(
            allowed=False,
            action="final_legal_advice",
            severity="blocked",
            reasons=["final legal advice and outcome guarantees are outside product boundaries"],
            explanation="I cannot provide final legal advice or outcome guarantees. I can organize evidence and surface attorney-review questions.",
        )

    if any(marker in lowered for marker in ["export packet", "download packet", "send packet", "share packet"]):
        return WorkflowGuardResult(
            allowed=True,
            action="packet_export",
            severity="caution",
            reasons=["packet export may contain sensitive matter material"],
            explanation="Before export, review source links, redactions, missing fields, and attorney-review status.",
            requires_confirmation=True,
        )

    if any(marker in lowered for marker in ["bulk ingest", "load folder", "import docket", "zip"]):
        return WorkflowGuardResult(
            allowed=True,
            action="bulk_ingest",
            severity="caution",
            reasons=["bulk ingest can introduce duplicates, unrelated material, or bad chronology"],
            explanation="Use matter-specific folders, preserve original filenames, and review the ingest queue after indexing.",
            requires_confirmation=False,
        )

    return WorkflowGuardResult(allowed=True, action="normal")


def evidence_handling_rules() -> list[str]:
    return [
        "Preserve original source names and timestamps where available.",
        "Treat OCR and pasted notes as derived material, not as the original evidence.",
        "Separate facts observed in source material from legal conclusions.",
        "Use citations and trace entries before drafting attorney-review packets.",
        "Do not delete or overwrite evidence without an audit-backed workflow.",
    ]

