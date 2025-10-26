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
import json
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

# Accept only standard dash bullets to avoid non-ASCII issues
_DASH_LINE_RX = re.compile(r"^\s*-\s+(.+?)\s*$")


def _simplify_for_layperson(text: str) -> str:
    """Very lightweight jargon simplifier for fallback mode (English only)."""
    repl = [
        (r"\babdomen(al)?\b", "tummy"),
        (r"\burinary tract\b", "urine system"),
        (r"\bureters\b", "ureters (urine tubes)"),
        (r"\bureter\b", "ureter (urine tube)"),
        (r"\blesions\b", "abnormal spots"),
        (r"\blesion\b", "abnormal spot"),
        (r"\bmass(es)?\b", "lump"),
        (r"\bneoplasm(s)?\b", "cancer"),
        (r"\blymphadenopathy\b", "swollen lymph nodes"),
        (r"\bhepatic\b", "liver"),
        (r"\brenal\b", "kidney"),
        (r"\bpulmonary\b", "lung"),
        (r"\bcervix\b", "cervix (neck of the womb)"),
        (r"\bhydronephrosis\b", "hydronephrosis (severe urine backup)"),
        (r"\bstenosis\b", "narrowing"),
        (r"\bdilat(e|ed|ation)\b", "widened/swollen"),
        (r"\bintravenous contrast\b", "iodine dye"),
        (r"\bcontrast\b", "iodine dye"),
        (r"\bmetastases\b", "spread of the cancer"),
        (r"\bmetastasis\b", "spread of the cancer"),
        (r"\bindeterminate\b", "unclear"),
        (r"\bbenign\b", "non-cancer"),
        (r"\bmalignant\b", "cancer"),
    ]
    out = text or ""
    for rx, rep in repl:
        out = re.sub(rx, rep, out, flags=re.IGNORECASE)
    return out


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


# Override to ensure a layperson-friendly style reference
REFERENCE_STYLE = (
    "You convert radiology reports into a kind, patient-facing summary. "
    "Use second person (you/your). Be confident and plain. Avoid hedging. "
    "Short to medium sentences (8–22 words) with everyday words. Define medical terms in brackets. "
    "Keep numbers; add simple size comparisons when helpful. Use direct verbs: shows, spreads into, blocks, likely spread."
)


def _compose_prompt(meta: Dict[str, str], secs: Dict[str, str], language: str) -> List[dict]:
    """Build a Responses API input payload requesting strict JSON with required keys."""
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
        "You convert radiology reports into a kind, patient-facing summary. "
        "Write ALL output ONLY in {language}. Do not include any personal identifiers."
    ).replace("{language}", language or "English")

    developer = (
        "Return ONLY a JSON object with keys: reason, technique, findings, conclusion, concern.\n"
        "Use second person (you/your). Be confident and plain. Avoid hedging.\n"
        "Explain as if to someone with no medical background (about grade 6 reading level).\n"
        "Use a kind, calm, supportive tone.\n\n"
        "STYLE & LENGTH\n"
        "- Short to medium sentences (8–22 words). Use everyday words.\n"
        "- Define any medical word immediately in brackets: 'hydronephrosis (severe urine backup)'.\n"
        "- Replace difficult words with plain ones (abdomen → tummy, lesion → abnormal spot, mass → lump).\n"
        "- No acronyms without a plain explanation the first time: CT (special x-ray), MRI (magnet pictures), IV (through a vein).\n"
        "- Keep numbers from the report. Add a simple size comparison in brackets when helpful.\n"
        "- Use direct verbs: shows, spreads into, blocks, has likely spread.\n"
        "- Do not use phrases like 'clinical correlation recommended' or 'please correlate'.\n\n"
        "READABILITY RULES\n"
        "- Prefer common words: urinary tract → urine system; ureter → urine tube; hydronephrosis → severe urine backup.\n"
        "- Avoid jargon: attenuation, morphology, heterogeneous, signal, density. Use simple alternatives or define in brackets.\n"
        "- Avoid fear language. Be honest but reassuring.\n\n"
        "MAP EACH FIELD TO THIS EXACT CONTENT\n\n"
        "reason:\n"
        "- 1–2 sentences. Explain why the scan was ordered in simple words.\n"
        "- Start with the patient's symptom or trigger.\n"
        "- Name body area(s) to check and for what (growths, blockages, bleeding).\n\n"
        "technique:\n"
        "- 1–2 sentences, friendly and concrete.\n"
        "- Mention modality, body area, thin slices, and contrast timing if used.\n\n"
        "findings:\n"
        "- Return either (A) a single string composed of bullet lines that each start with '- ', or (B) an array of bullet strings where each item starts with '- '.\n"
        "- Write exactly 3–4 bullets that cover the MAIN findings only.\n"
        "- Do NOT add a 'normal elsewhere' bullet — the UI adds this automatically.\n"
        "- Put the most important problem first. Each bullet may be 1–2 short sentences.\n"
        "- Use plain names (bladder, ureter (urine tube), kidney, womb (uterus), lung).\n"
        "- Show cause → effect clearly.\n\n"
        "conclusion:\n"
        "- 1–2 sentences that tie the findings together in plain language.\n"
        "- Name the main problem and key spread/blockage in one tight summary.\n\n"
        "concern:\n"
        "- 2–3 short sentences with next steps and red-flags. Use action words.\n"
        "- Include urgent referrals, likely procedures (e.g., stent or nephrostomy), and 'go to hospital if...' warnings.\n\n"
        "CRITICAL CONTENT RULES\n"
        "- Extract ONLY from the actual report. Do not invent findings.\n"
        "- Keep units and grades/stages as written; add simple explanations in brackets.\n"
        "- Prefer common words: abdomen → tummy; urinary tract → urine system; lesion → abnormal spot; mass → lump;\n"
        "  dilated → widened/swollen; stenosis → narrowing. Avoid fear language but do not downplay serious issues.\n\n"
        "OUTPUT FORMAT\n"
        "Return JSON only. No prose, no markdown, no headings, no prefix/suffix—just the object.\n"
        "STRICT JSON RULES: Valid JSON, no trailing commas, close all quotes/brackets/braces, and STOP after the final }.\n"
        "TOTAL BUDGET: Keep the entire JSON under 1200 characters."
    )

    user = (
        f"Study: {study or 'Unknown'}\n\n"
        f"Reason section:\n{secs.get('reason','').strip()}\n\n"
        f"Technique section:\n{secs.get('technique','').strip()}\n\n"
        f"Findings section:\n{secs.get('findings','').strip()}\n\n"
        f"Impression/Conclusion section:\n{secs.get('impression','').strip()}\n\n"
        f"REFERENCE STYLE: {REFERENCE_STYLE}"
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

    raw = "".join(out_text).strip()
    if raw:
        preview = raw if len(raw) <= 4000 else raw[:4000] + "…[truncated]"
        logger.info("GPT-5 raw output:%s\n%s", " (truncated)" if len(raw) > 4000 else "", preview)
    return raw


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


def _salvage_json_like(raw: str) -> Dict[str, object]:
    """Best-effort extraction when JSON is truncated or slightly malformed.

    Returns a dict with keys reason, technique, findings, conclusion, concern.
    findings may be a list[str] or a string of dash-lines.
    """
    out: Dict[str, object] = {"reason": "", "technique": "", "findings": "", "conclusion": "", "concern": ""}

    def grab_string(key: str) -> str:
        m = re.search(rf'"{key}"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"', raw, flags=re.S)
        if m:
            return (m.group(1) or "").strip()
        # Partial capture (no closing quote): take to end and trim to last sentence end
        m2 = re.search(rf'"{key}"\s*:\s*"(.*)$', raw, flags=re.S)
        if m2:
            val = (m2.group(1) or "").strip()
            # Trim to last ., !, or ? to avoid ragged endings
            cut = max(val.rfind("."), val.rfind("!"), val.rfind("?"))
            if cut != -1:
                val = val[: cut + 1]
            # Remove any trailing quotes/braces/commas
            val = val.rstrip('\'"} ,')
            return val.strip()
        return ""

    def grab_array(key: str) -> List[str]:
        m = re.search(rf'"{key}"\s*:\s*\[(.*?)\]', raw, flags=re.S)
        items: List[str] = []
        if m:
            body = m.group(1) or ""
            for s in re.findall(r'"([^"\\]*(?:\\.[^"\\]*)*)"', body, flags=re.S):
                s = (s or "").strip()
                if s:
                    items.append(s)
        return items

    reason = grab_string("reason")
    technique = grab_string("technique")
    findings_list = grab_array("findings")
    findings_str = grab_string("findings") if not findings_list else ""
    conclusion = grab_string("conclusion")
    concern = grab_string("concern")

    if reason:
        out["reason"] = reason
    if technique:
        out["technique"] = technique
    if findings_list:
        out["findings"] = findings_list
    elif findings_str:
        out["findings"] = findings_str
    if conclusion:
        out["conclusion"] = conclusion
    if concern:
        out["concern"] = concern

    return out

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
        # Fallback: build simple, layperson text directly from sections
        logger.warning("LLM output empty; using heuristic fallback")
        fallback = {
            "reason": secs.get("reason", "").strip(),
            "technique": secs.get("technique", "").strip(),
            "findings": secs.get("findings", "").strip(),
            "conclusion": secs.get("impression", "").strip(),
            "concern": "",
        }
        # Convert first N sentences, simplified
        def sentences(s: str, n: int = 5) -> List[str]:
            pts = re.split(r"(?<=[.!?])\s+", s)
            return [p.strip() for p in pts if p.strip()][:n]

        reason_txt = html.escape(" ".join(_simplify_for_layperson(x) for x in sentences(fallback["reason"], 2)))
        tech_txt = html.escape(" ".join(_simplify_for_layperson(x) for x in sentences(fallback["technique"], 2)))
        find_ul = _dashes_to_ul("\n".join(f"- {_simplify_for_layperson(s)}" for s in sentences(fallback["findings"], 6)))
        concl_txt = html.escape(" ".join(_simplify_for_layperson(x) for x in sentences(fallback["conclusion"], 2)))
        concern_txt = ""
    else:
        # Expect strict JSON; if not, fall back to section splitter
        try:
            parts_raw = json.loads(raw)
            if not isinstance(parts_raw, dict):
                raise ValueError("not a JSON object")
            parts = {k: (parts_raw.get(k) or "") for k in ("reason", "technique", "findings", "conclusion", "concern")}
        except Exception:
            logger.exception("Failed to parse JSON from GPT-5 output; attempting salvage of partial JSON")
            salvaged = _salvage_json_like(raw)
            if any(bool(salvaged.get(k)) for k in ("reason", "technique", "findings", "conclusion", "concern")):
                parts = salvaged
            else:
                logger.info("Salvage unsuccessful; falling back to section splitter")
                parts = _split_sections(raw)

        def _as_text(v: object) -> str:
            if isinstance(v, list):
                return " ".join(str(x).strip() for x in v if str(x).strip())
            return str(v or "").strip()

        def _as_bullets_text(v: object) -> str:
            if isinstance(v, list):
                bullets: list[str] = []
                for x in v:
                    s = str(x or "").strip()
                    if not s:
                        continue
                    if not s.startswith("- "):
                        s = "- " + s
                    bullets.append(s)
                return "\n".join(bullets)
            return str(v or "").strip()

        reason_txt = html.escape(_as_text(parts.get("reason")))
        tech_txt = html.escape(_as_text(parts.get("technique")))
        find_ul = _dashes_to_ul(_as_bullets_text(parts.get("findings")))
        concl_txt = html.escape(_as_text(parts.get("conclusion")))
        concern_txt = html.escape(_as_text(parts.get("concern")))

        # If concern looks truncated or missing, attempt a focused completion
        if len(_strip_html(concern_txt)) < 60:
            try:
                small_messages = [
                    {
                        "role": "system",
                        "content": (
                            "You write short, patient-facing next-step advice. "
                            "Use second person. Avoid identifiers. Write ONLY in {language}."
                        ).replace("{language}", language or "English"),
                    },
                    {
                        "role": "developer",
                        "content": (
                            "Return ONLY the Note of Concern text: 2–3 short sentences (<= 300 characters total). "
                            "Include urgent referrals, likely procedures, and clear red-flags (go to hospital if ...). "
                            "No markdown. No quotes. No JSON."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Context from report (plain text):\n"
                            f"Reason: {html.unescape(reason_txt)}\n"
                            f"Technique: {html.unescape(tech_txt)}\n"
                            f"Findings bullets: {re.sub(r'<[^>]+>', ' ', find_ul)}\n"
                            f"Conclusion: {html.unescape(concl_txt)}\n"
                            f"Draft concern (may be incomplete): {html.unescape(concern_txt)}\n"
                            "Write the final Note of Concern now."
                        ),
                    },
                ]
                refined = _call_gpt5(small_messages).strip()
                if refined:
                    concern_txt = html.escape(refined)
            except Exception:
                logger.exception("Concern refinement call failed; keeping salvaged text")

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
        "reason": reason_txt,
        "technique": tech_txt,
        "findings": find_ul,
        "conclusion": concl_txt,
        "concern": concern_txt,
    }

    # Basic word count for stats (cheap and local)
    blob = " ".join(
        _strip_html(out.get(k, ""))
        for k in ("reason", "technique", "findings", "conclusion", "concern")
    )
    out["word_count"] = len(blob.split())
    out["sentence_count"] = len(re.findall(r"[.!?]+", blob))

    return out
