from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class DriftState:
    alignment: float = 1.0
    trust: float = 1.0
    clarity: float = 1.0
    overload: float = 0.0
    repetition: float = 0.0
    contradiction: float = 0.0
    drift: float = 0.0
    reset_recommended: bool = False
    reasons: list[str] = field(default_factory=list)
    measured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class CollaborationProfile:
    staff_id: str
    user_name: str
    role: str
    assistant_role: str = "Legal workstation continuity partner for matter-scoped evidence, research, drafting, and review support."
    relationship_summary: str = "Preserve verified matter state, decisions, failures, working preferences, and next safe steps without pretending to restore a prior AI instance."
    communication_style: list[str] = field(default_factory=lambda: [
        "Speak plainly and directly.",
        "Prioritize source-linked legal work over generic chat.",
        "State uncertainty instead of inventing missing memory.",
        "Use matter evidence, CourtListener records, and trace history only when relevant.",
        "Surface failures clearly and recommend the next safe step.",
    ])
    working_preferences: list[str] = field(default_factory=lambda: [
        "Diagnose before redesigning.",
        "Preserve working evidence and trace records.",
        "Separate verified facts, inference, and attorney-review decisions.",
        "Do not repeat known workflow failures.",
    ])
    vocabulary: dict[str, str] = field(default_factory=lambda: {
        "continuity": "Preserve verified state, decisions, failures, next step, and working style.",
        "restore point": "The exact verified state from which work resumes.",
        "next safe step": "The smallest useful action that advances work without damaging the record.",
        "do not repeat": "Known failures or regressions that must not happen again.",
    })


class DriftMonitor:
    CORRECTION_PATTERNS = [
        r"that'?s not what i mean",
        r"you forgot",
        r"that'?s not true",
        r"you'?re slowing down",
        r"you are slowing down",
        r"you lost the plot",
        r"i already told you",
        r"refresh your memory",
        r"start over",
        r"continuity",
    ]
    CORRECTION_HARD_OVERRIDE = 3
    REPETITION_WINDOW = 4

    def __init__(self, threshold: float = 0.62, hard_threshold: float = 0.78) -> None:
        self.threshold = threshold
        self.hard_threshold = hard_threshold

    def evaluate(self, conversation: list[dict[str, str]], objective: str = "") -> DriftState:
        recent = conversation[-18:]
        user_text = " ".join(
            message.get("content", "") for message in recent if message.get("role") == "user"
        ).lower()
        corrections = sum(
            len(re.findall(pattern, user_text, flags=re.I))
            for pattern in self.CORRECTION_PATTERNS
        )
        contradiction = min(1.0, corrections / 5.0)
        repetition = self._repetition(recent)
        overload = min(1.0, sum(len(message.get("content", "")) for message in recent) / 30000.0)
        topic_drift = self._topic_drift(recent, objective)
        drift = min(
            1.0,
            contradiction * 0.35 + repetition * 0.25 + overload * 0.20 + topic_drift * 0.20,
        )

        reasons: list[str] = []
        if corrections >= 2:
            reasons.append(f"User corrected or reoriented the session {corrections} times.")
        if repetition >= 0.35:
            reasons.append("Responses are becoming repetitive.")
        if overload >= 0.45:
            reasons.append("The session is heavily loaded.")
        if topic_drift >= 0.45:
            reasons.append("The conversation is drifting from the active objective.")

        forced_reset = corrections >= self.CORRECTION_HARD_OVERRIDE
        if forced_reset:
            reasons.append(
                f"Hard override: {corrections} corrections >= {self.CORRECTION_HARD_OVERRIDE}; reset recommended regardless of composite score."
            )
        if drift >= self.hard_threshold:
            reasons.append("Fresh-session reset recommended.")
        elif drift >= self.threshold:
            reasons.append("Continuity refresh recommended.")

        return DriftState(
            alignment=round(1.0 - topic_drift, 3),
            trust=round(1.0 - contradiction, 3),
            clarity=round(1.0 - repetition, 3),
            overload=round(overload, 3),
            repetition=round(repetition, 3),
            contradiction=round(contradiction, 3),
            drift=round(drift, 3),
            reset_recommended=(drift >= self.threshold) or forced_reset,
            reasons=reasons,
        )

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 3}

    def _repetition(self, messages: list[dict[str, str]]) -> float:
        answers = [message.get("content", "") for message in messages if message.get("role") == "assistant"]
        scores: list[float] = []
        for index in range(1, len(answers)):
            current_tokens = self._tokens(answers[index])
            if not current_tokens:
                continue
            window_start = max(0, index - self.REPETITION_WINDOW)
            for prior_index in range(window_start, index):
                prior_tokens = self._tokens(answers[prior_index])
                if prior_tokens:
                    scores.append(len(current_tokens & prior_tokens) / len(current_tokens | prior_tokens))
        return max(scores, default=0.0)

    def _topic_drift(self, messages: list[dict[str, str]], objective: str) -> float:
        target = self._tokens(objective)
        if not target:
            return 0.0
        recent = self._tokens(" ".join(message.get("content", "") for message in messages[-6:]))
        return max(0.0, 1.0 - len(target & recent) / max(1, len(target)))


def profile_for_staff(staff: dict[str, Any]) -> CollaborationProfile:
    staff_id = str(staff.get("id") or staff.get("full_name") or "staff-member")
    role = str(staff.get("role") or "legal_staff")
    name = str(staff.get("full_name") or staff_id)
    preferences = list(staff.get("continuity_preferences") or [])
    profile = CollaborationProfile(staff_id=staff_id, user_name=name, role=role)
    if preferences:
        profile.working_preferences.extend(str(item) for item in preferences if str(item).strip())
    notes = str(staff.get("notes") or "").strip()
    if notes:
        profile.relationship_summary = f"{profile.relationship_summary} Staff note: {notes[:240]}"
    return profile


def trace_to_conversation(trace: dict[str, Any]) -> list[dict[str, str]]:
    if str(trace.get("event_type") or "") != "chat":
        return []
    user_text = str(trace.get("title") or trace.get("input") or "").strip()
    assistant_text = str(trace.get("summary") or trace.get("output") or "").strip()
    messages: list[dict[str, str]] = []
    if user_text:
        messages.append({"role": "user", "content": user_text})
    if assistant_text:
        messages.append({"role": "assistant", "content": assistant_text})
    return messages


def trace_matches_staff(trace: dict[str, Any], staff: dict[str, Any]) -> bool:
    staff_id = str(staff.get("id") or "").strip()
    if not staff_id:
        return False
    metadata = trace.get("metadata") if isinstance(trace.get("metadata"), dict) else {}
    candidate_values = {
        str(metadata.get("staff_id") or ""),
        str(metadata.get("attorney_id") or ""),
        str(metadata.get("prepared_by_id") or ""),
        str(metadata.get("reviewed_by_id") or ""),
        str(metadata.get("approved_by_id") or ""),
        str(metadata.get("signed_by_id") or ""),
        str(trace.get("staff_id") or ""),
    }
    return staff_id in candidate_values


def build_staff_continuity_status(
    *,
    staff_directory: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    enabled: bool,
    monitor: Optional[DriftMonitor] = None,
) -> dict[str, Any]:
    if not enabled:
        return {"enabled": False, "items": [], "reset_recommended": False, "profiles": 0}

    monitor = monitor or DriftMonitor()
    attorneys = [
        item for item in staff_directory
        if str(item.get("role") or "").lower() in {"attorney", "firm_administrator"}
        and item.get("active", True)
    ]
    chat_traces = [trace for trace in traces if str(trace.get("event_type") or "") == "chat"]
    items: list[dict[str, Any]] = []
    for staff in attorneys:
        profile = profile_for_staff(staff)
        matched = [trace for trace in chat_traces if trace_matches_staff(trace, staff)]
        used_fallback = False
        if not matched:
            matched = chat_traces
            used_fallback = True
        conversation: list[dict[str, str]] = []
        for trace in matched[-18:]:
            conversation.extend(trace_to_conversation(trace))
        state = monitor.evaluate(conversation, objective="legal matter continuity and attorney review workflow")
        items.append(
            {
                "staff_id": profile.staff_id,
                "user_name": profile.user_name,
                "role": profile.role,
                "profile": asdict(profile),
                "drift_state": asdict(state),
                "trace_count": len(matched),
                "fallback_shared_trace_stream": used_fallback,
            }
        )
    return {
        "enabled": True,
        "profiles": len(items),
        "reset_recommended": any(item["drift_state"]["reset_recommended"] for item in items),
        "items": items,
    }
