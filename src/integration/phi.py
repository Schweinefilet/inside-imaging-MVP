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
import hmac
import os
import re
from typing import Dict, Tuple

_REDACTED = "[redacted]"

# Names: honorific-prefixed ("Dr. Jane Smith") and common labeled demographic
# fields ("Patient Name: John Smith", "Patient: SMITH, JOHN", "Name: ...").
_NAME_RX = re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Dr|Prof)\.?\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}\b")
_LABELED_NAME_RX = re.compile(
    r"\b(?:Patient(?:'s)?[ \t]*Name|Patient|Name)[ \t]*[:\-][ \t]*"
    r"([A-Z][A-Za-z'\-]+(?:[ \t,]+[A-Z][A-Za-z'\-]+){0,3})"
)
_DOB_RX  = re.compile(
    r"\b(?:DOB|Date of Birth|D\.O\.B\.?|Birth\s*Date)\s*[:\-]?\s*\d{1,4}[/\-.]\d{1,2}[/\-.]\d{1,4}\b",
    re.IGNORECASE,
)
_MRN_RX  = re.compile(
    r"\b(?:MRN|Medical Record Number|Patient ID|Patient #|Patient No\.?|Hospital No\.?)\s*[:\-]?\s*[A-Z0-9\-]{4,}\b",
    re.IGNORECASE,
)
_SSN_RX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE_RX = re.compile(r"\b\+?\d{1,3}[\s\-.()]*\d{2,4}[\s\-.()]*\d{2,4}[\s\-.()]*\d{2,4}\b")
_EMAIL_RX = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

# Regex-based scrubbing cannot reliably catch every Safe Harbor identifier
# (unlabeled bare names in narrative prose, street addresses, device/vehicle
# IDs, ages >= 90). Treat this as a best-effort layer, not a certified
# de-identification guarantee, especially in "pseudonymize" mode where the
# text body itself is only partially scrubbed.

_DEV_ONLY_PEPPER = "dev-only-do-not-use-in-production"


def _pseudonym_secret() -> str:
    """Server-side secret used to key pseudonym hashes.

    Must NOT be derived only from data that lives alongside the pseudonym in
    the database (e.g. tenant_id) — that would let anyone with read access to
    the table recompute pseudonym(guess, tenant_id) for a small guess space
    and reverse it. Falls back to SECRET_KEY (also required in production by
    app.py) so no separate secret is required to opt in.
    """
    return os.getenv("PHI_PSEUDONYM_SECRET") or os.getenv("SECRET_KEY") or _DEV_ONLY_PEPPER


def pseudonym(value: str, salt: str = "") -> str:
    if not value:
        return ""
    secret = _pseudonym_secret()
    mac = hmac.new(secret.encode("utf-8"), (salt + ":" + value).encode("utf-8"), hashlib.sha256)
    return "p_" + mac.hexdigest()[:12]


def scrub_text(text: str, mode: str) -> str:
    if not text or mode == "passthrough":
        return text or ""
    if mode in ("pseudonymize", "full_deidentify"):
        out = _NAME_RX.sub(_REDACTED, text)
        out = _LABELED_NAME_RX.sub(_REDACTED, out)
        out = _DOB_RX.sub(_REDACTED, out)
        out = _MRN_RX.sub(_REDACTED, out)
        out = _SSN_RX.sub(_REDACTED, out)
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
        # Unlike pseudonymize, full_deidentify is meant to be Safe-Harbor-like —
        # the accession number is also a direct identifier here since nothing
        # is kept correlatable, so it must be redacted too.
        for k in ("patient_name", "patient_id", "accession_number"):
            if out.get(k):
                out[k] = _REDACTED
    return out


def normalize_mode(raw: str) -> str:
    raw = (raw or "passthrough").strip().lower()
    if raw not in ("passthrough", "pseudonymize", "full_deidentify"):
        return "passthrough"
    return raw
