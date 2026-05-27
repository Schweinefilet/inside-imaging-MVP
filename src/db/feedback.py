"""Feedback / corrections submitted by radiologists & reviewers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.db.connection import _format_timestamp, execute, fetch_all


_FEEDBACK_COLS = (
    "id, username, feedback_type, subject, original_text,"
    " corrected_text, description, status, created_at,"
    " reviewed_at, reviewed_by, admin_notes"
)


def _row_to_feedback(row) -> Dict[str, Any]:
    return {
        "id": row[0], "username": row[1], "feedback_type": row[2], "subject": row[3],
        "original_text": row[4] or "", "corrected_text": row[5] or "",
        "description": row[6] or "", "status": row[7],
        "created_at": _format_timestamp(row[8]),
        "reviewed_at": _format_timestamp(row[9]),
        "reviewed_by": row[10] or "", "admin_notes": row[11] or "",
    }


def submit_feedback(username: str, feedback_type: str, subject: str,
                    original: str = "", corrected: str = "",
                    description: str = "") -> int:
    return execute(
        """
        INSERT INTO feedback (
            username, feedback_type, subject, original_text,
            corrected_text, description, status
        ) VALUES (?, ?, ?, ?, ?, ?, 'pending')
        """,
        (username, feedback_type, subject, original, corrected, description),
    )


def get_all_feedback(status: Optional[str] = None) -> List[Dict[str, Any]]:
    if status:
        rows = fetch_all(
            f"SELECT {_FEEDBACK_COLS} FROM feedback WHERE status = ? ORDER BY created_at DESC",
            (status,),
        )
    else:
        rows = fetch_all(
            f"SELECT {_FEEDBACK_COLS} FROM feedback ORDER BY created_at DESC"
        )
    return [_row_to_feedback(r) for r in rows]


def update_feedback_status(feedback_id: int, status: str, reviewed_by: str,
                           admin_notes: str = "") -> None:
    execute(
        """
        UPDATE feedback
        SET status = ?, reviewed_at = CURRENT_TIMESTAMP, reviewed_by = ?, admin_notes = ?
        WHERE id = ?
        """,
        (status, reviewed_by, admin_notes, feedback_id),
    )


def get_user_feedback(username: str) -> List[Dict[str, Any]]:
    rows = fetch_all(
        f"SELECT {_FEEDBACK_COLS} FROM feedback WHERE username = ? ORDER BY created_at DESC",
        (username,),
    )
    return [_row_to_feedback(r) for r in rows]
