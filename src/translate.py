"""
Patient-friendly translation and structuring for radiology reports.

This module builds a simple, sectioned summary suitable for templates/result.html.
It uses GPT‑5 via the OpenAI Responses API (when allowed) to rewrite the
extracted report content into short, clear bullet points with the same tone and
length as the provided reference style. Dashes ("-") from the model output are
rendered as HTML bullet lists so they appear as bullets in result.html.
"""

from __future__ import annotations

import os
import re
import csv
import html
import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

from .parse import parse_metadata, sections_from_text

logger = logging.getLogger("insideimaging.translate")


# ------------------------------------------------------------
# Minimal glossary support (optional CSV at data/glossary.csv)
# ------------------------------------------------------------
@dataclass
class Glossary:
    terms: Dict[str, str]

    @classmethod
    def load(cls, path: str) -> "Glossary":
        terms: Dict[str, str] = {}
        try:
            with open(path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    term = (row.get("term") or row.get("Term") or "").strip()
                    definition = (row.get("definition") or row.get("Definition") or "").strip()
                    if term:
                        terms[term.lower()] = definition
        except Exception:
            logger.exception("Failed to load glossary from %s", path)
        return cls(terms)


# -----------------------
# HTML helper functions
# -----------------------
_DASH_LINE_RX = re.compile(r"^\s*[-•]\s+(.+?)\s*$")


def _dashes_to_ul(text: str) -> str:
    """Convert dash/•-prefixed lines to a <ul> list.

    If there are no dash bullets, return text as-is (HTML-escaped).
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
        # No bullets detected; return safe paragraph text
        return html.escape(text)

    lis = "".join(f"<li>{html.escape(it)}</li>" for it in items if it)
    return f"<ul>{lis}</ul>"


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s or "").strip()


# -----------------------
# GPT‑5 call + parsing
# -----------------------
REFERENCE_STYLE = (
    "For the reason for scan section: -You had blood in the urine, so the doctors needed clear "
    "pictures to look for growths or blockages in the bladder, ureters and kidneys. "
    "Procedure details section: -A CT machine took many thin pictures of your tummy before and after iodine dye "
    "was injected, giving sharp views of the urine system. "
    "Important Findings section: -A lump about 6 × 5 × 4½ cm (chicken-egg sized) grows from the left side of the bladder, "
    "both inside and outside the bladder wall. -The lump spreads into the lower part of the left urine tube (ureter), "
    "causing severe swelling of that tube and the left kidney (grade 5 hydronephrosis). -The same lump has also grown into "
    "the neck of the womb (cervix). -Several small spots are seen in both lower lungs; these likely show the cancer has spread. "
    "-Liver, spleen, pancreas, adrenal glands, bowel and big blood vessels look normal; spine shows age-related wear. "
    "CONCLUSION section: -Large bladder cancer has broken through the bladder wall, blocked the left ureter, invaded the cervix, "
    "and has probably spread to the lungs. NOTE OF CONCERN section: -See a urologist and cancer specialist urgently to plan biopsy, "
    "staging and treatment such as surgery, chemotherapy or immunotherapy. -The swollen kidney may need a stent or tube (nephrostomy) "
    "to drain urine and prevent damage. -Go to hospital fast if you get fever, severe side pain, cannot pass urine, or feel breathless."
)


def _compose_prompt(meta: Dict[str, str], secs: Dict[str, str], language: str) -> List[dict]:
    """Build a Responses API input payload with strict headings and dash bullets.

    We ask the model to emit EXACT headings so we can reliably parse them.
    """
    # Build minimal, PHI-free context
    study = (meta.get("study") or "").strip()
    hospital = (meta.get("hospital") or "").strip()
    if hospital:
        # keep institution name generic—do not surface PHI
        hospital = "a hospital"

    context = {
        "study": study,
        "hospital": hospital,
        "reason": secs.get("reason", ""),
        "technique": secs.get("technique", ""),
        "findings": secs.get("findings", ""),
        "impression": secs.get("impression", ""),
    }

    system = (
        "You rewrite radiology reports into clear, patient-friendly language. "
        "Do not include any personal identifiers (names, exact dates, medical record numbers)."
    )

    # Developer message with format contract
    developer = (
        "Write a short summary in English with EXACTLY these headings and ONLY dash-prefixed bullets under each:\n"
        "Reason for the scan:\n"
        "- ...\n\n"
        "Procedure details:\n"
        "- ...\n\n"
        "Important Findings:\n"
        "- ...\n\n"
        "CONCLUSION:\n"
        "- ...\n\n"
        "NOTE OF CONCERN:\n"
        "- ...\n\n"
        "Follow the tone, feel and general length of the REFERENCE exactly."
    )

    # User message provides the actual report content and the reference style
    user = (
        "REFERENCE (style and length to emulate):\n"
        f"{REFERENCE_STYLE}\n\n"
        "REPORT CONTEXT (from the uploaded report—use only what is relevant, avoid PHI):\n"
        f"Study: {study or 'Unknown'}\n"
        f"Reason section:\n{secs.get('reason','').strip()}\n\n"
        f"Technique section:\n{secs.get('technique','').strip()}\n\n"
        f"Findings section:\n{secs.get('findings','').strip()}\n\n"
        f"Impression/Conclusion section:\n{secs.get('impression','').strip()}\n\n"
        "Instructions:\n"
        "- Use plain words a non-medical reader understands.\n"
        "- Keep each bullet to 1 short sentence.\n"
        "- Do NOT invent facts beyond the report context.\n"
        "- Do NOT include names, dates, or identifiers.\n"
        "- Output only the five sections with the exact headings and dash bullets."
    )

    # Responses API accepts a list of messages; we'll pass role-tagged messages.
    return [
        {"role": "system", "content": system},
        {"role": "developer", "content": developer},
        {"role": "user", "content": user},
    ]


def _call_gpt5(messages: List[dict]) -> str:
    """Call the OpenAI Responses API with GPT‑5 and return raw text output.

    Honors environment variables:
      - OPENAI_MODEL (default: gpt-5)
      - INSIDEIMAGING_ALLOW_LLM (must be truthy to call)
      - OPENAI_MAX_OUTPUT_TOKENS (default: 256)
      - OPENAI_TIMEOUT (seconds; default: 60)
    """
    allow = os.getenv("INSIDEIMAGING_ALLOW_LLM", "0").strip()
    if allow not in ("1", "true", "True", "yes", "YES"):  # guardrails
        logger.info("LLM disabled by INSIDEIMAGING_ALLOW_LLM=%r", allow)
        return ""

    # Lazy import so the app can run without the SDK in non-LLM mode
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        logger.exception("openai SDK not available; skipping LLM call")
        return ""

    model = os.getenv("OPENAI_MODEL", "gpt-5").strip() or "gpt-5"
    max_out = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "256") or 256)
    timeout_s = int(os.getenv("OPENAI_TIMEOUT", "60") or 60)

    # Some deployments pin verbosity low to encourage brevity
    text_cfg = {"verbosity": "low"}

    client = OpenAI()

    try:
        resp = client.responses.create(
            model=model,
            input=messages,
            text=text_cfg,
            max_output_tokens=max_out,
            reasoning={"effort": "minimal"},  # fast, deterministic rewriting
            timeout=timeout_s,
        )
    except Exception:
        logger.exception("OpenAI responses.create failed")
        return ""

    # Extract assistant text per the SDK pattern
    out_text = []
    try:
        for item in getattr(resp, "output", []) or []:
            if hasattr(item, "content"):
                for c in getattr(item, "content", []) or []:
                    if hasattr(c, "text") and c.text:
                        out_text.append(c.text)
    except Exception:
        logger.exception("Failed to parse OpenAI response output")
        return ""

    return "".join(out_text).strip()


def _split_sections(raw: str) -> Dict[str, str]:
    """Split raw model text into our five sections by fixed headings.

    Expected headings (case-insensitive):
      - Reason for the scan:
      - Procedure details:
      - Important Findings:
      - CONCLUSION:
      - NOTE OF CONCERN:
    """
    if not raw:
        return {"reason": "", "technique": "", "findings": "", "conclusion": "", "concern": ""}

    # Normalize headings and split
    normalized = raw.replace("\r", "")
    # Build regex to capture each heading and following block
    parts_rx = re.compile(
        r"(?is)\b(Reason for the scan|Procedure details|Important Findings|CONCLUSION|NOTE OF CONCERN)\s*:\s*\n?"
        r"(.*?)(?=\n\s*(?:Reason for the scan|Procedure details|Important Findings|CONCLUSION|NOTE OF CONCERN)\s*:|\Z)"
    )

    found: Dict[str, str] = {}
    for m in parts_rx.finditer(normalized):
        key = m.group(1).lower()
        body = (m.group(2) or "").strip()
        if key.startswith("reason"):
            found["reason"] = body
        elif key.startswith("procedure"):
            found["technique"] = body
        elif key.startswith("important"):
            found["findings"] = body
        elif key.startswith("conclusion"):
            found["conclusion"] = body
        elif key.startswith("note of concern"):
            found["concern"] = body

    # Ensure all keys are present
    for k in ("reason", "technique", "findings", "conclusion", "concern"):
        found.setdefault(k, "")
    return found


# -----------------------
# Public interface
# -----------------------
def build_structured(report_text: str, glossary: Optional[Glossary] = None, *, language: str = "English") -> Dict[str, str]:
    """Create the structured, patient-friendly output consumed by result.html.

    Returns a dict with keys: reason, technique, findings, conclusion, concern, and
    a nested patient dict with non-identifying metadata when available.
    """
    text = report_text or ""
    cleaned = _strip_html(text)

    # Parse metadata and sections from the raw report
    try:
        meta = parse_metadata(cleaned)
    except Exception:
        logger.exception("parse_metadata failed")
        meta = {"hospital": "", "study": "", "name": "", "sex": "", "age": "", "date": ""}

    try:
        secs = sections_from_text(cleaned)
    except Exception:
        logger.exception("sections_from_text failed")
        secs = {"reason": "", "technique": "", "findings": cleaned, "impression": ""}

    # Compose and call GPT‑5
    messages = _compose_prompt(meta, secs, language)
    raw = _call_gpt5(messages)

    if not raw:
        # Fallback: build very simple bullets directly from sections
        logger.warning("LLM output empty; using heuristic fallback")
        fallback = {
            "reason": secs.get("reason", "").strip(),
            "technique": secs.get("technique", "").strip(),
            "findings": secs.get("findings", "").strip(),
            "conclusion": secs.get("impression", "").strip(),
            "concern": "",
        }
        # Convert first 1–5 sentences per section into bullets
        def sentences(s: str, n: int = 5) -> List[str]:
            pts = re.split(r"(?<=[.!?])\s+", s)
            return [p.strip() for p in pts if p.strip()][:n]

        reason_ul = _dashes_to_ul("\n".join(f"- {s}" for s in sentences(fallback["reason"], 1)))
        tech_ul = _dashes_to_ul("\n".join(f"- {s}" for s in sentences(fallback["technique"], 1)))
        find_ul = _dashes_to_ul("\n".join(f"- {s}" for s in sentences(fallback["findings"], 6)))
        concl_ul = _dashes_to_ul("\n".join(f"- {s}" for s in sentences(fallback["conclusion"], 3)))
        concern_ul = ""
    else:
        parts = _split_sections(raw)
        reason_ul = _dashes_to_ul(parts.get("reason", ""))
        tech_ul = _dashes_to_ul(parts.get("technique", ""))
        find_ul = _dashes_to_ul(parts.get("findings", ""))
        concl_ul = _dashes_to_ul(parts.get("conclusion", ""))
        concern_ul = _dashes_to_ul(parts.get("concern", ""))

    # Patient block: omit name/identifiers; keep generic study fields
    patient = {
        "hospital": meta.get("hospital", ""),
        "study": meta.get("study", "Unknown"),
        "name": "",  # ensure PHI is stripped
        "sex": meta.get("sex", ""),
        "age": meta.get("age", ""),
        "date": meta.get("date", ""),
        "history": secs.get("reason", ""),
    }

    out = {
        "patient": patient,
        "reason": reason_ul,
        "technique": tech_ul,
        "findings": find_ul,
        "conclusion": concl_ul,
        "concern": concern_ul,
    }

    # Basic word count for stats (cheap and local)
    blob = " ".join(
        _strip_html(out.get(k, ""))
        for k in ("reason", "technique", "findings", "conclusion", "concern")
    )
    out["word_count"] = len(blob.split())
    out["sentence_count"] = len(re.findall(r"[.!?]+", blob))

    return out

