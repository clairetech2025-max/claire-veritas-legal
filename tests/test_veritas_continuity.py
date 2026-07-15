from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

import web.app as app_module
from web.services.continuity import DriftMonitor, build_staff_continuity_status, profile_for_staff
from web.services.workspace import WorkspaceStore


def test_drift_monitor_clean_conversation_does_not_reset():
    monitor = DriftMonitor()
    result = monitor.evaluate(
        [
            {"role": "user", "content": "Please summarize the evidence timeline."},
            {"role": "assistant", "content": "I will summarize the dated evidence and cite the source records."},
            {"role": "user", "content": "Include the hearing dates."},
            {"role": "assistant", "content": "The hearing dates are included with source references."},
        ],
        objective="summarize evidence timeline",
    )
    assert result.reset_recommended is False


def test_drift_monitor_three_corrections_force_reset():
    monitor = DriftMonitor()
    result = monitor.evaluate(
        [
            {"role": "user", "content": "That's not what I mean, you forgot the case context."},
            {"role": "assistant", "content": "I will reconsider the case context."},
            {"role": "user", "content": "I already told you this, refresh your memory."},
            {"role": "assistant", "content": "I will reconsider the case context."},
            {"role": "user", "content": "You lost the plot, start over."},
        ],
        objective="repair continuity",
    )
    assert result.reset_recommended is True
    assert any("Hard override" in reason for reason in result.reasons)


def test_drift_monitor_non_adjacent_repetition_detected():
    monitor = DriftMonitor()
    result = monitor.evaluate(
        [
            {"role": "assistant", "content": "The source trace links every finding to evidence."},
            {"role": "assistant", "content": "Next I will inspect the matter profile."},
            {"role": "assistant", "content": "The attorney packet remains draft-only."},
            {"role": "assistant", "content": "The source trace links every finding to evidence."},
        ]
    )
    assert result.repetition > 0.5


def test_continuity_profile_is_built_per_staff_member():
    profile = profile_for_staff(
        {
            "id": "attorney-1",
            "full_name": "Jordan Lee",
            "role": "attorney",
            "continuity_preferences": ["Prefer short source-linked answers."],
        }
    )
    assert profile.staff_id == "attorney-1"
    assert profile.user_name == "Jordan Lee"
    assert "Prefer short source-linked answers." in profile.working_preferences


def test_staff_continuity_status_uses_staff_chat_traces_and_flags_reset():
    status = build_staff_continuity_status(
        enabled=True,
        staff_directory=[{"id": "attorney-1", "full_name": "Jordan Lee", "role": "attorney", "active": True}],
        traces=[
            {
                "event_type": "chat",
                "title": "That's not what I mean, you forgot the evidence.",
                "summary": "I will reconsider the evidence.",
                "metadata": {"staff_id": "attorney-1"},
            },
            {
                "event_type": "chat",
                "title": "I already told you this, refresh your memory.",
                "summary": "I will reconsider the evidence.",
                "metadata": {"staff_id": "attorney-1"},
            },
            {
                "event_type": "chat",
                "title": "You lost the plot, start over.",
                "summary": "I will reconsider the evidence.",
                "metadata": {"staff_id": "attorney-1"},
            },
        ],
    )
    assert status["enabled"] is True
    assert status["profiles"] == 1
    assert status["reset_recommended"] is True
    assert status["items"][0]["drift_state"]["reset_recommended"] is True


def test_veritas_health_continuity_is_feature_flagged(monkeypatch):
    with tempfile.TemporaryDirectory() as td:
        store = WorkspaceStore(Path(td))
        previous = app_module.STORE
        app_module.STORE = store
        client = TestClient(app_module.app)
        try:
            store.upsert_staff_member({"id": "attorney-1", "full_name": "Jordan Lee", "role": "attorney"})
            store.append_trace(
                {
                    "event_type": "chat",
                    "title": "That's not what I mean, you forgot the evidence.",
                    "summary": "I will reconsider the evidence.",
                    "metadata": {"staff_id": "attorney-1"},
                }
            )
            store.append_trace(
                {
                    "event_type": "chat",
                    "title": "I already told you this, refresh your memory.",
                    "summary": "I will reconsider the evidence.",
                    "metadata": {"staff_id": "attorney-1"},
                }
            )
            store.append_trace(
                {
                    "event_type": "chat",
                    "title": "You lost the plot, start over.",
                    "summary": "I will reconsider the evidence.",
                    "metadata": {"staff_id": "attorney-1"},
                }
            )

            monkeypatch.delenv("VERITAS_FIRM_TIER_CONTINUITY", raising=False)
            disabled = client.get("/health").json()["firm_tier_continuity"]
            assert disabled["enabled"] is False

            monkeypatch.setenv("VERITAS_FIRM_TIER_CONTINUITY", "true")
            enabled = client.get("/health").json()["firm_tier_continuity"]
            assert enabled["enabled"] is True
            assert enabled["reset_recommended"] is True
            assert enabled["items"][0]["staff_id"] == "attorney-1"
        finally:
            app_module.STORE = previous
