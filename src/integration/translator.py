"""Adapter that runs the Inside Imaging translation pipeline on integration payloads."""

from __future__ import annotations

import io
import logging
import re
from typing import Any, Dict, Optional

try:
    from pdfminer.high_level import extract_text as _pdfminer_extract
except Exception:
    _pdfminer_extract = None


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    if not _pdfminer_extract:
        raise RuntimeError("pdfminer.six is required to extract PDF text")
    return _pdfminer_extract(io.BytesIO(pdf_bytes)) or ""


def normalize_report_text(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"\r\n?", "\n", text)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def run_translation(report_text: str, language: str = "English") -> Dict[str, Any]:
    """Run the existing build_structured pipeline; return a dict ready for the
    Patient's Copy template."""
    from app import LAY_GLOSS, build_structured  # late import to avoid cycle at module load

    text = normalize_report_text(report_text)
    if not text:
        raise ValueError("Report text is empty")

    try:
        structured = build_structured(text, LAY_GLOSS, language=language) or {}
    except Exception:
        logging.exception("build_structured failed in integration pipeline")
        structured = {}

    patient = (structured.get("patient") if isinstance(structured.get("patient"), dict) else {}) or {}

    return {
        "structured": {
            "reason": structured.get("reason", "") or "",
            "technique": structured.get("technique", "") or "",
            "findings": structured.get("findings", "") or "",
            "conclusion": structured.get("conclusion", "") or "",
            "concern": structured.get("concern", "") or "",
        },
        "patient": {
            "name": patient.get("name", "") or structured.get("name", ""),
            "age": patient.get("age", "") or structured.get("age", ""),
            "sex": patient.get("sex", "") or structured.get("sex", ""),
            "date": patient.get("date", "") or structured.get("date", ""),
            "hospital": patient.get("hospital", "") or structured.get("hospital", ""),
            "study": patient.get("study", "") or structured.get("study", "Unknown"),
        },
        "language": language,
    }
