from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from memory_io import append_jsonl
from veritas_bias_guard import BiasGuardResult, evaluate_bias_and_safety
from veritas_teacher_mode import active_correction_rules, handle_teacher_mode
from veritas_workflow_guard import WorkflowGuardResult, evaluate_workflow_request, evidence_handling_rules


@dataclass
class VeritasRuntimeResult:
    mode: str
    lane: str
    reply_override: str | None = None
    system_context: str = ""
    user_notice: str = ""
    bias: BiasGuardResult = field(default_factory=lambda: BiasGuardResult(True))
    workflow: WorkflowGuardResult = field(default_factory=lambda: WorkflowGuardResult(True, "normal"))
    correction: dict[str, Any] = field(default_factory=dict)
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "lane": self.lane,
            "reply_override": self.reply_override,
            "system_context": self.system_context,
            "user_notice": self.user_notice,
            "bias": self.bias.to_dict(),
            "workflow": self.workflow.to_dict(),
            "correction": self.correction,
            "trace": self.trace,
        }


class VeritasClaireRuntime:
    """
    Product-scoped Claire Runtime for Veritas Legal.

    This is not the global CLAIRE brain. It is a bounded runtime adapter for
    legal evidence intake, workflow coaching, source discipline, packet safety,
    correction learning, and matter-level audit continuity.
    """

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.trace_path = self.root / "memory" / "veritas_runtime_traces.jsonl"

    def handle_message(
        self,
        *,
        message: str,
        case_id: str | None = None,
        matter: dict[str, Any] | None = None,
        memory_status: dict[str, Any] | None = None,
        citations: list[dict[str, Any]] | None = None,
        user_id: str = "local_user",
        session_id: str = "web_chat",
    ) -> VeritasRuntimeResult:
        matter = matter or {}
        memory_status = memory_status or {}
        citations = citations or []
        lane = self.classify_lane(message)
        has_sources = bool(citations or int(memory_status.get("evidence", 0) or 0))

        correction = handle_teacher_mode(
            message,
            root=self.root,
            user_id=user_id,
            session_id=session_id,
            original_prompt=message,
        )
        if correction.get("detected"):
            result = VeritasRuntimeResult(
                mode="teacher_mode",
                lane="CORRECTION_LEARNING",
                reply_override=str(correction.get("reply") or ""),
                correction=correction,
            )
            self._trace(result, message=message, case_id=case_id, matter=matter)
            return result

        workflow = evaluate_workflow_request(message)
        bias = evaluate_bias_and_safety(message, has_sources=has_sources)

        if not workflow.allowed:
            result = VeritasRuntimeResult(
                mode="blocked",
                lane=lane,
                reply_override=workflow.explanation,
                workflow=workflow,
                bias=bias,
                user_notice=workflow.explanation,
            )
            self._trace(result, message=message, case_id=case_id, matter=matter)
            return result

        if self._is_onboarding_request(message):
            reply = self.onboarding_reply(matter=matter, memory_status=memory_status)
            result = VeritasRuntimeResult(mode="onboarding", lane="ONBOARDING", reply_override=reply, workflow=workflow, bias=bias)
            self._trace(result, message=message, case_id=case_id, matter=matter)
            return result

        if self._is_guide_request(message):
            reply = self.guide_reply(matter=matter, memory_status=memory_status, citations=citations)
            result = VeritasRuntimeResult(mode="guided_workflow", lane="GUIDED_WORKFLOW", reply_override=reply, workflow=workflow, bias=bias)
            self._trace(result, message=message, case_id=case_id, matter=matter)
            return result

        system_context = self.system_context(
            lane=lane,
            matter=matter,
            memory_status=memory_status,
            workflow=workflow,
            bias=bias,
        )
        notice_parts = []
        if workflow.requires_confirmation:
            notice_parts.append(workflow.explanation)
        if not bias.approved:
            notice_parts.extend(bias.guidance)
        result = VeritasRuntimeResult(
            mode="supervised_generation",
            lane=lane,
            system_context=system_context,
            user_notice=" ".join(notice_parts).strip(),
            workflow=workflow,
            bias=bias,
        )
        self._trace(result, message=message, case_id=case_id, matter=matter)
        return result

    def classify_lane(self, message: str) -> str:
        text = str(message or "").lower()
        if any(term in text for term in ["onboard", "first time", "teach me", "how do i use"]):
            return "ONBOARDING"
        if "courtlistener" in text or "court listener" in text or "recap" in text:
            return "COURT_LISTENER_WORKFLOW"
        if any(term in text for term in ["packet", "export", "draft", "attorney review", "memo", "brief", "motion"]):
            return "PACKET_PREP"
        if any(term in text for term in ["guide me", "next step", "what should i do", "workflow"]):
            return "GUIDED_WORKFLOW"
        if any(term in text for term in ["timeline", "chronology", "date sequence"]):
            return "TIMELINE_REVIEW"
        if any(term in text for term in ["evidence", "upload", "ocr", "source", "citation", "exhibit"]):
            return "EVIDENCE_INTAKE"
        return "LEGAL_WORKSPACE_CHAT"

    def system_context(
        self,
        *,
        lane: str,
        matter: dict[str, Any],
        memory_status: dict[str, Any],
        workflow: WorkflowGuardResult,
        bias: BiasGuardResult,
    ) -> str:
        corrections = active_correction_rules(self.root)
        lines = [
            "Veritas Claire Runtime: product-scoped legal workspace supervision.",
            f"Lane: {lane}.",
            "Stay bounded to legal evidence intake, case organization, timelines, citations, packet preparation, and user coaching.",
            "CourtListener workflow: distinguish user evidence, CourtListener public case law, RECAP docket/document data, and generated analysis.",
            "Warn that CourtListener/RECAP can be partial or stale and is not the official court docket when verification matters.",
            "Do not provide final legal advice, court filing instructions, outcome predictions, or attorney replacement.",
            "Current truth: Veritas Legal is a guided evidence-intake and case-organization workspace for attorney-review support.",
            "Evidence handling rules:",
            *[f"- {rule}" for rule in evidence_handling_rules()],
        ]
        if matter:
            lines.append(f"Active matter: {matter.get('case_id') or 'unassigned'} / {matter.get('title') or 'untitled'}.")
        lines.append(
            f"Workspace status: documents={memory_status.get('documents', 0)}, evidence={memory_status.get('evidence', 0)}, traces={memory_status.get('traces', 0)}."
        )
        if workflow.severity == "caution":
            lines.append(f"Workflow caution: {workflow.explanation}")
        if not bias.approved:
            lines.append("Bias/safety guard guidance: " + " ".join(bias.guidance))
        if corrections:
            lines.append("Active Veritas correction rules:")
            for record in corrections:
                lines.append(f"- {record.get('inferred_rule')}")
        return "\n".join(lines)

    def onboarding_reply(self, *, matter: dict[str, Any], memory_status: dict[str, Any]) -> str:
        matter_name = matter.get("title") or matter.get("case_id") or "the active matter"
        return (
            f"I will guide you through Veritas Legal for {matter_name}. Start by creating or selecting the matter, "
            "then add documents, photos, notes, OCR text, expenses, communications, and docket exports. "
            "After ingest, review the source trail, timeline, evidence categories, and missing-information checklist. "
            "When the record is organized, generate an attorney-review packet. This workspace organizes evidence for review; "
            "it is not legal advice and does not replace attorneys."
        )

    def guide_reply(
        self,
        *,
        matter: dict[str, Any],
        memory_status: dict[str, Any],
        citations: list[dict[str, Any]],
    ) -> str:
        if not matter or not matter.get("case_id"):
            return "Next step: create or select a matter before ingesting evidence so every source lands in the correct case workspace."
        if int(memory_status.get("documents", 0) or 0) == 0 and int(memory_status.get("evidence", 0) or 0) == 0:
            return "Next step: ingest source material. Upload files, paste OCR text, import a docket, or load a matter folder. Preserve original filenames and source context."
        if not citations:
            return "Next step: search the record and inspect citations before asking for analysis or packet drafting. Grounded sources protect packet integrity."
        return "Next step: run analysis, review anomalies and missing fields, then draft an attorney-review packet with redactions enabled."

    def review_answer(self, answer: str, *, has_sources: bool = False) -> BiasGuardResult:
        return evaluate_bias_and_safety(answer, has_sources=has_sources)

    def _trace(self, result: VeritasRuntimeResult, *, message: str, case_id: str | None, matter: dict[str, Any]) -> None:
        record = {
            "trace_id": self._trace_id(message),
            "timestamp_ns": time.time_ns(),
            "case_id": case_id or matter.get("case_id") or "unassigned",
            "message_hash": hashlib.sha256(str(message).encode("utf-8", errors="ignore")).hexdigest(),
            "mode": result.mode,
            "lane": result.lane,
            "workflow": result.workflow.to_dict(),
            "bias": result.bias.to_dict(),
            "correction_saved": bool(result.correction.get("saved")),
            "reply_override": bool(result.reply_override),
            "scope": "veritas_legal_product",
        }
        result.trace = record
        append_jsonl(str(self.trace_path), record)

    def _trace_id(self, message: str) -> str:
        digest = hashlib.sha256(f"{time.time_ns()}|{message}".encode("utf-8", errors="ignore")).hexdigest()[:16]
        return f"vcr_{digest}"

    def _is_onboarding_request(self, message: str) -> bool:
        text = str(message or "").lower()
        return any(marker in text for marker in ["onboard", "first time", "teach me how to use", "new user"])

    def _is_guide_request(self, message: str) -> bool:
        text = str(message or "").lower()
        if any(marker in text for marker in ["draft", "memo", "brief", "motion", "packet", "analysis"]):
            return False
        return any(marker in text for marker in ["guide me", "next step", "what should i do next", "workflow help"])
