from __future__ import annotations

from typing import Any, Dict, Optional

from correction_learning import detect_correction, learn_from_correction
from correction_store import CorrectionStore


def maybe_handle_teacher_mode(
    message: str,
    *,
    original_prompt: str = "",
    wrong_answer_excerpt: str = "",
    user_id: str = "local_user",
    session_id: str = "local_session",
    store: Optional[CorrectionStore] = None,
) -> Dict[str, Any]:
    if not detect_correction(message):
        return {"detected": False}
    return learn_from_correction(
        message,
        original_prompt=original_prompt,
        wrong_answer_excerpt=wrong_answer_excerpt,
        user_id=user_id,
        session_id=session_id,
        store=store,
    )

