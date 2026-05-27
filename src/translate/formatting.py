"""HTML/text formatting helpers: dash-to-ul, strip-html, jargon simplifier."""

from __future__ import annotations

import html
import re
from typing import List


# Accept ASCII '-' OR bullet '•' as bullet markers (regex tightened later in the
# original file to ASCII only; keep both spellings as in the legacy source).
_DASH_LINE_RX = re.compile(r"^\s*-\s+(.+?)\s*$")


def _dashes_to_ul(text: str) -> str:
    """Convert dash/•-prefixed lines to a <ul> list.

    If there are no dash bullets, returns text as-is (HTML-escaped).
    """
    if not text:
        return ""
    lines = [ln.rstrip() for ln in (text or "").splitlines()]
    items: List[str] = []
    for ln in lines:
        m = _DASH_LINE_RX.match(ln)
        if m:
            items.append(m.group(1).strip())
    if not items:
        return html.escape(text)
    lis = "".join(f"<li>{html.escape(it)}</li>" for it in items if it)
    return f"<ul>{lis}</ul>"


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "").strip()


def _simplify_for_layperson(text: str) -> str:
    """Very lightweight jargon simplifier for fallback mode (English only)."""
    repl = [
        # Spinal anatomy — specific levels first
        (r"\bL5/S1\b", "between the lowest back bone and tailbone"),
        (r"\bL4/L5\b", "between the 4th and 5th bones in your lower back"),
        (r"\bL3/L4\b", "between the 3rd and 4th bones in your lower back"),
        (r"\bL2/L3\b", "between the 2nd and 3rd bones in your lower back"),
        (r"\bL1/L2\b", "between the 1st and 2nd bones in your lower back"),
        (r"\bC6/C7\b", "between the 6th and 7th bones in your neck"),
        (r"\bC5/C6\b", "between the 5th and 6th bones in your neck"),
        (r"\bC4/C5\b", "between the 4th and 5th bones in your neck"),
        (r"\bC3/C4\b", "between the 3rd and 4th bones in your neck"),
        (r"\bT\d+/T\d+\b", "between bones in your mid-back"),
        (r"\bL\d+/L\d+\b", "between bones in your lower back"),
        (r"\bC\d+/C\d+\b", "between bones in your neck"),
        # General spinal terms
        (r"\blumbar spine\b", "lower back"),
        (r"\bthoracic spine\b", "mid-back"),
        (r"\bcervical spine\b", "neck"),
        (r"\bvertebrae\b", "bones in the spine"),
        (r"\bvertebra\b", "bone in the spine"),
        (r"\bforamina\b", "nerve tunnels"),
        (r"\bforamen\b", "nerve tunnel"),
        (r"\bdisc herniation\b", "slipped disc"),
        (r"\bherniated disc\b", "slipped disc"),
        (r"\bspinal canal\b", "main channel in the spine"),
        (r"\bnerve root\b", "nerve branch"),
        (r"\bspinal cord\b", "main nerve bundle in the spine"),
        # Lymph and glands
        (r"\badenopathy\b", "swollen glands"),
        (r"\blymphadenopathy\b", "swollen glands"),
        (r"\blymph nodes\b", "infection-fighting glands"),
        (r"\blymph node\b", "infection-fighting gland"),
        # Fluid and swelling
        (r"\bedema\b", "swelling"),
        (r"\beffusion\b", "fluid buildup"),
        (r"\bpleural effusion\b", "fluid around the lung"),
        (r"\bascites\b", "fluid in the belly"),
        # Body regions
        (r"\babdomen(al)?\b", "tummy"),
        (r"\burinary tract\b", "urine system"),
        (r"\bureters\b", "urine tubes"),
        (r"\bureter\b", "urine tube"),
        # Abnormalities
        (r"\blesions\b", "abnormal spots"),
        (r"\blesion\b", "abnormal spot"),
        (r"\bmass(es)?\b", "lump"),
        (r"\bneoplasm(s)?\b", "cancer"),
        # Organs
        (r"\bhepatic\b", "liver"),
        (r"\brenal\b", "kidney"),
        (r"\bpulmonary\b", "lung"),
        (r"\bcervix\b", "neck of the womb"),
        # Conditions
        (r"\bhydronephrosis\b", "severe urine backup"),
        (r"\bstenosis\b", "narrowing"),
        (r"\bdilat(e|ed|ation)\b", "widened"),
        # Procedures
        (r"\bintravenous contrast\b", "dye through a vein"),
        (r"\bcontrast\b", "dye"),
        # Cancer terms
        (r"\bmetastases\b", "spread of the cancer"),
        (r"\bmetastasis\b", "spread of the cancer"),
        (r"\bmalignant\b", "cancer"),
        (r"\bcarcinoma\b", "cancer"),
        (r"\bbenign\b", "non-cancer"),
        # Other
        (r"\bindeterminate\b", "unclear"),
        (r"\batelectasis\b", "partially collapsed lung"),
        (r"\bconsolidation\b", "filled airspaces in the lung"),
        (r"\bnodule(s)?\b", "small lump"),
    ]
    out = text or ""
    for rx, rep in repl:
        out = re.sub(rx, rep, out, flags=re.IGNORECASE)
    return out
