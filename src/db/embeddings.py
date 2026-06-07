"""Embedding generation and storage for radiologist feedback records.

Uses OpenAI text-embedding-3-small. Embeddings are stored as packed
little-endian 32-bit floats (BLOB) in feedback.embedding.
Respects INSIDEIMAGING_ALLOW_LLM — returns None silently when LLM is off.

Embedding source: raw_report_text (the original hospital report fed to the AI),
NOT the AI-simplified output. This ensures that at inference time the cosine
similarity is raw-medical-text vs raw-medical-text, which is meaningful.

Trigger: approved status only. Implemented is an admin tracking state and
does not gate the retrieval pool. Superseded corrections are excluded.
"""

from __future__ import annotations

import logging
import math
import os
import struct
from typing import List, Optional

from src.db.connection import execute, fetch_all, fetch_one

logger = logging.getLogger("insideimaging.db.embeddings")

_EMBEDDING_MODEL = "text-embedding-3-small"


# --- codec ------------------------------------------------------------------

def _encode_embedding(vec: List[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


def _decode_embedding(blob: bytes) -> List[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if not norm_a or not norm_b:
        return 0.0
    return dot / (norm_a * norm_b)


# --- OpenAI call ------------------------------------------------------------

def embed_text(text: str) -> Optional[List[float]]:
    """Return an embedding vector for text, or None if LLM is disabled / call fails."""
    allow = os.getenv("INSIDEIMAGING_ALLOW_LLM", "0").strip()
    if allow not in ("1", "true", "True", "yes", "YES"):
        logger.debug("LLM disabled; skipping embedding")
        return None
    try:
        from openai import OpenAI  # type: ignore
        client = OpenAI()
        resp = client.embeddings.create(model=_EMBEDDING_MODEL, input=text.strip())
        return resp.data[0].embedding
    except Exception:
        logger.exception("Embedding API call failed (model=%s)", _EMBEDDING_MODEL)
        return None


# --- per-record hook --------------------------------------------------------

def embed_feedback_record(feedback_id: int) -> bool:
    """Generate and store an embedding for one approved feedback record.

    Embeds raw_report_text — the original hospital report text that was fed
    to the AI — so that retrieval compares incoming raw reports against stored
    raw reports (apples-to-apples similarity).

    Called only when a record is set to 'approved'. Returns True on success.
    """
    row = fetch_one(
        """
        SELECT raw_report_text FROM feedback
        WHERE id = ?
          AND corrected_text IS NOT NULL AND corrected_text != ''
          AND embedding IS NULL
          AND status = 'approved'
        """,
        (feedback_id,),
    )
    if not row or not row[0]:
        return False
    vec = embed_text(row[0])
    if vec is None:
        return False
    execute("UPDATE feedback SET embedding = ? WHERE id = ?", (_encode_embedding(vec), feedback_id))
    logger.info("Stored embedding for feedback id=%d (source=raw_report_text)", feedback_id)
    return True


# --- backfill ---------------------------------------------------------------

def embed_approved_feedback() -> int:
    """Embed every approved (non-superseded) record with raw_report_text but no embedding.

    Safe to run repeatedly. Returns the number of records successfully embedded.
    """
    rows = fetch_all(
        """
        SELECT id, raw_report_text FROM feedback
        WHERE status = 'approved'
          AND corrected_text IS NOT NULL AND corrected_text != ''
          AND raw_report_text IS NOT NULL AND raw_report_text != ''
          AND embedding IS NULL
        """,
    )
    count = 0
    for row in rows:
        fid, raw = row[0], row[1]
        if not raw:
            continue
        vec = embed_text(raw)
        if vec is None:
            logger.warning("Embedding failed for feedback id=%d; skipping", fid)
            continue
        execute("UPDATE feedback SET embedding = ? WHERE id = ?", (_encode_embedding(vec), fid))
        count += 1
        logger.info("Backfilled embedding for feedback id=%d", fid)
    return count
