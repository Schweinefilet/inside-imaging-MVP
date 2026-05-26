"""PHI scrubber for integration payloads.

Three modes, chosen per-tenant via the `tenants.phi_mode` column:
  - passthrough        : no modification (default; appropriate when the hospital
                         is the only data subject and you're already within
                         their PHI boundary)
  - pseudonymize       : replace direct identifiers with stable hashed tokens so
                         the same patient/accession across calls remains
                         correlatable internally but not identifiable
  - full_deidentify    : strip every direct identifier and replace with
                         "[redacted]" tokens (matches the HIPAA Safe Harbor
                         spirit; not formally certified)

These functions operate on the *report-level* metadata dict that flows through
the integration pipeline. The actual radiology text body is also redacted on
heuristic name/date patterns when not in passthrough mode.
"""

from __future__ import annotations

import hashlib
import re
from typing import Dict, Tuple

_REDACTED = "[redacted]"

_NAME_RX = re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b")
_DOB_RX  = re.compile(r"\b(?:DOB|Date of Birth|D\.O\.B\.?)\s*[:\-]?\s*\d{1,4}[/\-.]\d{1,2}[/\-.]\d{1,4}\b", re.IGNORECASE)
_MRN_RX  = re.compile(r"\b(?:MRN|Medical Record Number|Patient ID|Patient #)\s*[:\-]?\s*[A-Z0-9\-]{4,}\b", re.IGNORECASE)
_PHONE_RX = re.compile(r"\b\+?\d{1,3}[\s\-.()]*\d{2,4}[\s\-.()]*\d{2,4}[\s\-.()]*\d{2,4}\b")
_EMAIL_RX = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")


def pseudonym(value: str, salt: str = "") -> str:
    if not value:
        return ""
    h = hashlib.sha256((salt + ":" + value).encode("utf-8")).hexdigest()
    return "p_" + h[:12]


def scrub_text(text: str, mode: str) -> str:
    if not text or mode == "passthrough":
        return text or ""
    if mode in ("pseudonymize", "full_deidentify"):
        out = _NAME_RX.sub(_REDACTED, text)
        out = _DOB_RX.sub(_REDACTED, out)
        out = _MRN_RX.sub(_REDACTED, out)
        out = _PHONE_RX.sub(_REDACTED, out)
        out = _EMAIL_RX.sub(_REDACTED, out)
        return out
    return text


def scrub_metadata(meta: Dict[str, str], mode: str, tenant_salt: str = "") -> Dict[str, str]:
    """Return a new metadata dict with identifiers handled per `mode`.
    Caller passes the per-tenant salt so that pseudonyms aren't cross-tenant correlatable."""
    if mode == "passthrough":
        return dict(meta)

    out = dict(meta)
    if mode == "pseudonymize":
        if out.get("patient_name"):
            out["patient_name"] = pseudonym(out["patient_name"], tenant_salt)
        if out.get("patient_id"):
            out["patient_id"] = pseudonym(out["patient_id"], tenant_salt)
        # Keep accession number — it's the operational link to the study
    elif mode == "full_deidentify":
        for k in ("patient_name", "patient_id"):
            if out.get(k):
                out[k] = _REDACTED
    return out


def normalize_mode(raw: str) -> str:
    raw = (raw or "passthrough").strip().lower()
    if raw not in ("passthrough", "pseudonymize", "full_deidentify"):
        return "passthrough"
    return raw
