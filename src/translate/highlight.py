"""Highlight clinically reassuring vs. concerning terms in findings/conclusion text.

Produces the `ii-pos` / `ii-neg` span markup that templates/result.html and
templates/patient_copy.html already style, and that app.py already counts
into the "Highlighted positive/negative" badges (see report_stats in app.py).
The original generator (translate.py's _wrap_green/_wrap_red/_highlight_phrasewise)
was dropped in the Oct 2025 rewrite that split translate.py into this package
and was never reintroduced for the new LLM-based pipeline, leaving those
badges permanently at 0/0. This reuses the negation-aware matching already
hardened in flag.py rather than the old module's cruder whole-sentence check.
"""

from __future__ import annotations

import html
import re
from typing import Dict, List, Tuple

from src.translate.flag import _is_negated

_POS_WORDS = ["normal", "benign", "unremarkable", "clear", "symmetric", "intact", "stable", "improved"]

_NEG_WORDS = [
    "mass", "tumor", "cancer", "lesion", "adenopathy", "enlarged", "necrotic", "metastasis",
    "obstruction", "compression", "invasion", "perforation", "ischemia", "fracture", "bleed",
    "hydroureteronephrosis", "hydroureter", "hydronephrosis", "herniation", "shift", "edema",
    "swelling", "atrophy", "stenosis", "anomaly",
]

_NEG_PHRASES = ["mass effect", "subfalcine herniation", "midline shift", "perilesional edema"]

_NEG_DEFS: Dict[str, str] = {
    "mass": "an abnormal lump that can press on tissue",
    "tumor": "a growth that forms a lump",
    "cancer": "a harmful growth that can spread",
    "lesion": "an abnormal spot or area",
    "adenopathy": "swollen lymph nodes",
    "enlarged": "bigger than normal",
    "necrotic": "dead tissue",
    "metastasis": "spread to other areas",
    "obstruction": "a blockage",
    "compression": "being pressed or squeezed by something",
    "invasion": "growing into nearby tissues",
    "perforation": "a hole or tear",
    "ischemia": "low blood flow",
    "fracture": "a broken bone",
    "bleed": "bleeding",
    "herniation": "tissue pushed out of its normal position",
    "edema": "swelling with fluid buildup",
    "atrophy": "shrinking or wasting of tissue",
    "stenosis": "narrowing of a passage or canal",
    "anomaly": "difference from typical anatomy",
    "mass effect": "pressure on nearby structures",
    "subfalcine herniation": "brain shifted under the central fold",
    "midline shift": "brain pushed off center",
    "perilesional edema": "swelling around the lesion",
}

_NEG_RX = re.compile(
    r"\b(" + "|".join(
        [p.replace(" ", r"\s+") for p in _NEG_PHRASES] + [re.escape(w) for w in _NEG_WORDS]
    ) + r")\b",
    re.IGNORECASE,
)
_POS_RX = re.compile(r"\b(" + "|".join(_POS_WORDS) + r")\b", re.IGNORECASE)
# Whole "no X" / "without X" phrases read as reassuring even when X isn't in
# _NEG_WORDS (e.g. "no significant abnormality") — wrap the full phrase green.
_NEG_LEAD_RX = re.compile(r"\b(?:no|without)\s+[a-z][a-z/-]*(?:\s+[a-z][a-z/-]*){0,3}", re.IGNORECASE)


def _wrap_pos(token: str) -> str:
    return f'<span class="ii-pos" style="color:#22c55e;font-weight:600">{html.escape(token)}</span>'


def _wrap_neg(token: str, defn: str = "") -> str:
    data = f' data-def="{html.escape(defn)}"' if defn else ""
    return f'<span class="ii-neg" style="color:#ef4444;font-weight:600"{data}>{html.escape(token)}</span>'


def highlight_text(text: str) -> str:
    """Wrap concerning terms in `.ii-neg` and reassuring/negated terms in
    `.ii-pos`. Takes plain (unescaped) text; returns escaped, safe HTML."""
    if not text:
        return ""

    matches: List[Tuple[int, int, str, str]] = []
    for m in _NEG_RX.finditer(text):
        matches.append((m.start(), m.end(), "neg", m.group(0).lower()))
    for m in _POS_RX.finditer(text):
        matches.append((m.start(), m.end(), "pos", ""))
    for m in _NEG_LEAD_RX.finditer(text):
        matches.append((m.start(), m.end(), "pos", ""))

    # Resolve overlaps: earliest start wins; on a tie, the longer match wins
    # (so "no fracture" as one phrase beats the nested bare "fracture").
    matches.sort(key=lambda t: (t[0], -(t[1] - t[0])))

    out: List[str] = []
    cursor = 0
    for start, end, kind, key in matches:
        if start < cursor:
            continue
        out.append(html.escape(text[cursor:start]))
        token = text[start:end]
        if kind == "neg":
            if _is_negated(text, start):
                out.append(_wrap_pos(token))
            else:
                out.append(_wrap_neg(token, _NEG_DEFS.get(key, "")))
        else:
            out.append(_wrap_pos(token))
        cursor = end
    out.append(html.escape(text[cursor:]))
    return "".join(out)


_LI_RX = re.compile(r"<li>(.*?)</li>", re.S)


def highlight_bullets_html(ul_html: str) -> str:
    """Re-render each `<li>` in a `<ul>...</ul>` string (as produced by
    formatting._dashes_to_ul, whose item text is plain html.escape'd) with
    ii-pos/ii-neg term highlighting."""
    if not ul_html or "<li>" not in ul_html:
        return ul_html

    def repl(m: "re.Match[str]") -> str:
        return f"<li>{highlight_text(html.unescape(m.group(1)))}</li>"

    return _LI_RX.sub(repl, ul_html)
