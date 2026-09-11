import re
from typing import Dict

# ---------------------------------------------------------------------------
# Negation helpers
# ---------------------------------------------------------------------------

_NEGATION_RE = re.compile(
    r"\b(no|not|without|negative\s+for|benign)\b",
    re.IGNORECASE,
)

# "not benign" / "non-benign" is a hedge toward malignancy, not a negation of it —
# without this, "benign" in the negation list above would wrongly cancel out a
# nearby cancer term in phrasing like "atypical, not benign; malignancy suspected".
_NOT_BENIGN_RE = re.compile(r"\b(?:not|non)[\s-]+benign\b", re.IGNORECASE)

# Negation words must apply within the same sentence/list item as the match —
# otherwise a negation earlier in a numbered impression list (e.g. "1. No
# fracture. 2. New mass, suspicious for malignancy.") can wrongly be treated as
# negating an unrelated, unnegated finding later in the report.
_CLAUSE_BREAK_RE = re.compile(r"[.!?;\n]|(?<=\s)\d{1,2}[.)](?=\s)")


def _clause_start(text: str, pos: int) -> int:
    """Index where the sentence/clause containing pos begins."""
    start = 0
    for m in _CLAUSE_BREAK_RE.finditer(text, 0, pos):
        start = m.end()
    return start


def _is_negated(text: str, match_start: int) -> bool:
    """True if a negation term applies to the match: within the same
    sentence/clause and within the 6 words before match_start."""
    clause_start = _clause_start(text, match_start)
    pre = text[clause_start:match_start]
    tokens = list(re.finditer(r"\b\w+\b", pre))
    if not tokens:
        return False
    window_start = tokens[-6].start() if len(tokens) >= 6 else 0
    window = pre[window_start:]
    if _NOT_BENIGN_RE.search(window):
        return False
    return bool(_NEGATION_RE.search(window))


def _has_unnegated(pattern: re.Pattern, text: str) -> bool:
    """True if the pattern matches at least once without a preceding negation."""
    return any(not _is_negated(text, m.start()) for m in pattern.finditer(text))


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Direct cancer/malignancy terms — negation-aware.
# Note: "cannot exclude malignancy" is handled here too — "cannot"/"exclude" are
# not negation words, so the cancer term passes through unnegated.
_CANCER_RE = re.compile(
    r"\b(malignancy|malignant|carcinoma|carcinomatosis|sarcoma|lymphoma|leukemia|"
    r"melanoma|neoplasm|neoplasia|metastasis|metastatic|cancer)\b",
    re.IGNORECASE,
)

# Structured reporting scores 4/5 — unambiguous clinical notation, no negation check.
_RADS_SCORE_RE = re.compile(
    r"\b(?:BI[- ]?RADS|LI[- ]?RADS|PI[- ]?RADS|Lung[- ]?RADS|TI[- ]?RADS)"
    r"\s*(?:category\s*|score\s*)?[45][A-Z]?\b",
    re.IGNORECASE,
)

# Suspicious/concerning phrases — negation-aware.
_SUSPICIOUS_RE = re.compile(
    r"\b(suspicious\s+for|concerning\s+for|highly\s+suspicious|worrisome\s+for"
    r"|raises?\s+concern\s+for)\b",
    re.IGNORECASE,
)

_BIOPSY_RE = re.compile(
    r"\b(recommend\s+biopsy|biopsy\s+recommended)\b",
    re.IGNORECASE,
)

_NEW_FINDING_RE = re.compile(
    r"\b(new\s+mass|new\s+lesion|newly\s+identified)\b",
    re.IGNORECASE,
)

_LYMPHOVASCULAR_RE = re.compile(
    r"\blymphovascular\s+invasion\b",
    re.IGNORECASE,
)

# "tumor" only when within ~5 words of "new", "suspicious", or "concerning" — negation-aware.
_TUMOR_PAIRED_RE = re.compile(
    r"\b(?:new|suspicious|concerning)\b(?:\W+\w+){0,5}\W*\btumor\b"
    r"|\btumor\b(?:\W+\w+){0,5}\W*\b(?:new|suspicious|concerning)\b",
    re.IGNORECASE,
)

# Inherently suspicious phrasing — no negation check needed.
_CANNOT_BE_EXCLUDED_RE = re.compile(
    r"\bcannot\s+be\s+excluded\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_report_sensitivity(text: str) -> Dict[str, bool]:
    """Scan raw report text for patterns indicating a potentially serious diagnosis.

    Returns {"flagged": True} if any sensitive pattern is found, {"flagged": False} otherwise.
    Designed as a standalone utility — tighten patterns here without touching routing logic.
    """
    if not text:
        return {"flagged": False}

    if _has_unnegated(_CANCER_RE, text):
        return {"flagged": True}

    if _RADS_SCORE_RE.search(text):
        return {"flagged": True}

    if _has_unnegated(_SUSPICIOUS_RE, text):
        return {"flagged": True}

    if _has_unnegated(_BIOPSY_RE, text):
        return {"flagged": True}

    if _has_unnegated(_NEW_FINDING_RE, text):
        return {"flagged": True}

    if _has_unnegated(_LYMPHOVASCULAR_RE, text):
        return {"flagged": True}

    if _CANNOT_BE_EXCLUDED_RE.search(text):
        return {"flagged": True}

    if _has_unnegated(_TUMOR_PAIRED_RE, text):
        return {"flagged": True}

    return {"flagged": False}
