"""Feedback / corrections submitted by radiologists & reviewers."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.db.connection import _format_timestamp, execute, fetch_all, fetch_one, get_connection

logger = logging.getLogger("insideimaging.db.feedback")

_FEEDBACK_COLS = (
    "id, username, feedback_type, subject, original_text,"
    " corrected_text, description, status, created_at,"
    " reviewed_at, reviewed_by, admin_notes, modality, ai_output, report_id"
)

# Canonical modalities used for filtering in retrieval and the portal UI.
KNOWN_MODALITIES = ("MRI", "CT", "X-RAY", "ULTRASOUND", "PET", "MAMMOGRAM")


def _extract_modality(study: str) -> str:
    """Return the canonical modality prefix from a study/modality string, or ''."""
    sl = (study or "").upper()
    for m in KNOWN_MODALITIES:
        if sl.startswith(m) or f" {m}" in f" {sl}":
            return m
    return ""


def _row_to_feedback(row) -> Dict[str, Any]:
    return {
        "id": row[0], "username": row[1], "feedback_type": row[2], "subject": row[3],
        "original_text": row[4] or "", "corrected_text": row[5] or "",
        "description": row[6] or "", "status": row[7],
        "created_at": _format_timestamp(row[8]),
        "reviewed_at": _format_timestamp(row[9]),
        "reviewed_by": row[10] or "", "admin_notes": row[11] or "",
        "modality": row[12] or "", "ai_output": row[13] or "",
        "report_id": row[14],
    }


def submit_feedback(
    username: str,
    feedback_type: str,
    subject: str,
    original: str = "",
    corrected: str = "",
    description: str = "",
    ai_output: str = "",
    modality: str = "",
    report_id: Optional[int] = None,
    raw_report_text: str = "",
) -> int:
    return execute(
        """
        INSERT INTO feedback (
            username, feedback_type, subject, original_text,
            corrected_text, description, status, ai_output, modality,
            report_id, raw_report_text
        ) VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
        """,
        (username, feedback_type, subject, original, corrected, description,
         ai_output, modality, report_id, raw_report_text),
    )


def get_reviewed_report_ids(username: str) -> set:
    """Return the set of patient report IDs this user has submitted any feedback for."""
    rows = fetch_all(
        "SELECT DISTINCT report_id FROM feedback WHERE username = ? AND report_id IS NOT NULL",
        (username,),
    )
    return {row[0] for row in rows}


def get_all_feedback(status: Optional[str] = None) -> List[Dict[str, Any]]:
    if status is not None:
        rows = fetch_all(
            f"SELECT {_FEEDBACK_COLS} FROM feedback WHERE status = ? ORDER BY created_at DESC",
            (status,),
        )
    else:
        rows = fetch_all(
            f"SELECT {_FEEDBACK_COLS} FROM feedback ORDER BY created_at DESC"
        )
    return [_row_to_feedback(r) for r in rows]


def update_feedback_status(
    feedback_id: int,
    status: str,
    reviewed_by: str,
    admin_notes: str = "",
) -> None:
    execute(
        """
        UPDATE feedback
        SET status = ?, reviewed_at = CURRENT_TIMESTAMP, reviewed_by = ?, admin_notes = ?
        WHERE id = ?
        """,
        (status, reviewed_by, admin_notes, feedback_id),
    )

    # Item 6: when approving, supersede any older approved/implemented correction
    # for the same report so only one canonical correction enters the retrieval pool.
    if status == "approved":
        row = fetch_one("SELECT report_id FROM feedback WHERE id = ?", (feedback_id,))
        report_id = row[0] if row and row[0] else None
        if report_id:
            execute(
                """
                UPDATE feedback
                SET status = 'superseded', embedding = NULL
                WHERE report_id = ?
                  AND id != ?
                  AND status IN ('approved', 'implemented')
                """,
                (report_id, feedback_id),
            )
            logger.info(
                "Superseded older corrections for report_id=%d (new canonical id=%d)",
                report_id, feedback_id,
            )

    # Item 2: embed only on approved, not implemented.
    if status == "approved":
        try:
            from src.db.embeddings import embed_feedback_record
            embed_feedback_record(feedback_id)
        except Exception:
            logger.warning(
                "Post-approval embedding failed for feedback id=%d", feedback_id, exc_info=True
            )


def get_user_feedback(username: str) -> List[Dict[str, Any]]:
    rows = fetch_all(
        f"SELECT {_FEEDBACK_COLS} FROM feedback WHERE username = ? ORDER BY created_at DESC",
        (username,),
    )
    return [_row_to_feedback(r) for r in rows]


def get_few_shot_examples(
    report_text: str,
    modality: str = "",
    limit: int = 3,
) -> List[Dict[str, Any]]:
    """Return up to `limit` radiologist-corrected examples most similar to report_text.

    Item 1: compares incoming raw report text against stored raw_report_text embeddings.
    Item 3: queries same-modality records first; falls back to cross-modality only
            when same-modality pool has fewer than `limit` candidates.
    Item 6: excludes superseded records.

    Returns dicts with original_text, ai_output, corrected_text.
    Returns [] silently when LLM is off or no candidates exist.
    """
    from src.db.embeddings import embed_text, _decode_embedding, _cosine

    query_vec = embed_text(report_text)
    if query_vec is None:
        return []

    query_modality = _extract_modality(modality)

    def _score_rows(rows: list) -> list:
        scored = []
        for row in rows:
            ai_out, corrected, blob = row[0], row[1], row[2]
            try:
                stored_vec = _decode_embedding(bytes(blob))
            except Exception:
                continue
            sim = _cosine(query_vec, stored_vec)
            scored.append((sim, ai_out or "", corrected or ""))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored

    base_query = """
        SELECT ai_output, corrected_text, embedding
        FROM feedback
        WHERE status = 'approved'
          AND corrected_text IS NOT NULL AND corrected_text != ''
          AND embedding IS NOT NULL
          AND raw_report_text IS NOT NULL AND raw_report_text != ''
    """

    # Same-modality pass
    same_modal: list = []
    if query_modality:
        rows_same = fetch_all(
            base_query + " AND UPPER(modality) LIKE ?",
            (f"{query_modality}%",),
        )
        same_modal = _score_rows(rows_same)

    if len(same_modal) >= limit:
        return [{"original_text": "", "ai_output": s[1], "corrected_text": s[2]}
                for s in same_modal[:limit]]

    # Cross-modality fallback — avoid duplicates already in same_modal
    already = {(s[1], s[2]) for s in same_modal}
    if query_modality:
        rows_cross = fetch_all(
            base_query + " AND UPPER(modality) NOT LIKE ?",
            (f"{query_modality}%",),
        )
    else:
        rows_cross = fetch_all(base_query)

    cross = [s for s in _score_rows(rows_cross) if (s[1], s[2]) not in already]

    combined = same_modal + cross
    combined.sort(key=lambda x: x[0], reverse=True)
    return [{"original_text": "", "ai_output": s[1], "corrected_text": s[2]}
            for s in combined[:limit]]


def get_feedback_by_id(feedback_id: int) -> Optional[Dict[str, Any]]:
    row = fetch_one(f"SELECT {_FEEDBACK_COLS} FROM feedback WHERE id = ?", (feedback_id,))
    return _row_to_feedback(row) if row else None


def update_feedback(
    feedback_id: int,
    username: str,
    feedback_type: str,
    subject: str,
    original: str = "",
    corrected: str = "",
    description: str = "",
) -> bool:
    """Update a pending feedback record owned by username. Returns True if a row was updated."""
    conn = get_connection()
    try:
        cur = conn.execute(
            """
            UPDATE feedback
               SET feedback_type = ?, subject = ?, original_text = ?,
                   corrected_text = ?, description = ?
             WHERE id = ? AND username = ? AND status = 'pending'
            """,
            (feedback_type, subject, original, corrected, description, feedback_id, username),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_feedback(feedback_id: int, username: str) -> bool:
    """Delete a pending feedback record owned by username. Returns True if deleted."""
    conn = get_connection()
    try:
        cur = conn.execute(
            "DELETE FROM feedback WHERE id = ? AND username = ? AND status = 'pending'",
            (feedback_id, username),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_feedback_metrics() -> List[Dict[str, Any]]:
    """Compute per-modality, per-feedback_type quality metrics.

    Returns rows with: modality, feedback_type, total_reviews, good_count,
    correction_count, correction_rate, avg_days_to_first_review.
    """
    rows = fetch_all(
        """
        SELECT
            COALESCE(NULLIF(f.modality, ''), 'Unknown')  AS modality,
            f.feedback_type,
            COUNT(*)                                     AS total_reviews,
            SUM(CASE WHEN f.feedback_type = 'no_changes' THEN 1 ELSE 0 END) AS good_count,
            SUM(CASE WHEN f.feedback_type != 'no_changes' THEN 1 ELSE 0 END) AS correction_count,
            AVG(
                CASE
                    WHEN f.report_id IS NOT NULL AND p.created_at IS NOT NULL
                    THEN CAST(
                        (julianday(f.created_at) - julianday(p.created_at))
                        AS REAL)
                    ELSE NULL
                END
            ) AS avg_days_to_review
        FROM feedback f
        LEFT JOIN patients p ON p.id = f.report_id
        WHERE f.status NOT IN ('superseded')
        GROUP BY modality, f.feedback_type
        ORDER BY modality, f.feedback_type
        """
    )
    results = []
    for row in rows:
        total = row[2] or 0
        correction = row[4] or 0
        results.append({
            "modality": row[0],
            "feedback_type": (row[1] or "").replace("_", " ").title(),
            "total_reviews": total,
            "good_count": row[3] or 0,
            "correction_count": correction,
            "correction_rate": round(correction / total, 3) if total else 0.0,
            "avg_days_to_review": round(row[5], 1) if row[5] is not None else None,
        })
    return results
