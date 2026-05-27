"""End-to-end translation pipeline: report text → structured patient-friendly summary."""

from __future__ import annotations

import html
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

from src.parse import parse_metadata, sections_from_text
from src.translate.formatting import (
    _dashes_to_ul,
    _simplify_for_layperson,
    _strip_html,
)
from src.translate.glossary import Glossary
from src.translate.kiswahili import _is_kiswahili, _to_kiswahili
from src.translate.openai_client import _call_gpt5
from src.translate.parsing import _salvage_json_like, _split_sections
from src.translate.prompts import _compose_prompt

logger = logging.getLogger("insideimaging.translate.pipeline")

_FIELDS = ("reason", "technique", "findings", "conclusion", "concern")


# --- small helpers ----------------------------------------------------------

def _sentences(s: str, n: int = 5) -> List[str]:
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+", s or "") if p.strip()][:n]


def _as_text(v: Any) -> str:
    if isinstance(v, list):
        return " ".join(str(x).strip() for x in v if str(x).strip())
    return str(v or "").strip()


def _as_bullets_text(v: Any) -> str:
    if isinstance(v, list):
        return "\n".join(("- " + s if not s.startswith("- ") else s)
                         for s in (str(x or "").strip() for x in v) if s)
    return str(v or "").strip()


def _simplify_then_translate(text: str, language: str) -> str:
    """Run the jargon simplifier, optionally re-translating into Kiswahili."""
    out = _simplify_for_layperson(text)
    return _to_kiswahili(out) if _is_kiswahili(language) else out


def _build_fallback(secs: Dict[str, str], language: str) -> Dict[str, str]:
    """Heuristic fallback when the LLM is disabled or returns nothing."""
    def chunk(key: str, n: int) -> List[str]:
        return [_simplify_then_translate(s, language) for s in _sentences(secs.get(key, ""), n)]

    reason = " ".join(chunk("reason", 2))
    tech = " ".join(chunk("technique", 2))
    findings_lines = chunk("findings", 6)
    concl = " ".join(chunk("conclusion" if "conclusion" in secs else "impression", 2))

    return {
        "reason": html.escape(reason),
        "technique": html.escape(tech),
        "findings": _dashes_to_ul("\n".join(f"- {s}" for s in findings_lines)),
        "conclusion": html.escape(concl),
        "concern": "",
    }


# --- LLM output parsing -----------------------------------------------------

def _parse_llm_output(raw: str) -> Dict[str, object]:
    """Try strict JSON → salvage of partial JSON → section splitter."""
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return {k: (obj.get(k) or "") for k in _FIELDS}
    except Exception:
        logger.info("Strict JSON parse failed; attempting salvage")

    salvaged = _salvage_json_like(raw)
    if any(salvaged.get(k) for k in _FIELDS):
        return salvaged

    return _split_sections(raw)  # type: ignore[return-value]


def _gpt_with_retry(messages: List[dict]) -> str:
    raw = _call_gpt5(messages)
    if not raw or raw.strip().endswith("}"):
        return raw
    logger.warning("GPT output truncated; retrying with higher token limit")
    original_max = os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "512")
    os.environ["OPENAI_MAX_OUTPUT_TOKENS"] = "800"
    try:
        retry = _call_gpt5(messages)
    finally:
        os.environ["OPENAI_MAX_OUTPUT_TOKENS"] = original_max
    return retry if retry and len(retry) > len(raw) else raw


def _translate_parts_via_llm(parts: Dict[str, object], *, language: str) -> Optional[Dict[str, object]]:
    """Ask the LLM to translate already-parsed parts into the target language."""
    if os.getenv("INSIDEIMAGING_ALLOW_LLM", "0") not in ("1", "true", "True", "yes", "YES"):
        return None

    system = (
        "You translate patient-facing medical text into {language} ONLY. "
        "Use a warm, clear, supportive tone."
    ).replace("{language}", language or "Kiswahili")
    if _is_kiswahili(language):
        system += (
            " Use pure Kiswahili; do NOT mix languages. Avoid English words entirely. "
            "You may keep CT/MRI/IV/X-ray acronyms but explain them in Kiswahili in brackets the first time."
        )

    developer = (
        "Return ONLY a JSON object with keys: reason, technique, findings, conclusion, concern.\n"
        "RULES:\n"
        "- Translate content fully into the target language; no English words.\n"
        "- Keep numbers, units, grades/stages as-is.\n"
        "- Keep acronyms (CT, MRI) but explain in the target language the first time in brackets.\n"
        "- findings must be either (A) an array of bullet strings starting with '- ', or (B) a dash-bullet string.\n"
        "- Do not add or remove bullets. JSON only — no prose, headings, or extra keys."
    )
    user = (
        "Translate the following JSON fields into the target language, preserving structure and bullets.\n"
        + json.dumps({k: parts.get(k, "") for k in _FIELDS}, ensure_ascii=False)
    )
    raw = _call_gpt5([
        {"role": "system", "content": system},
        {"role": "developer", "content": developer},
        {"role": "user", "content": user},
    ])
    if not raw:
        return None
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            for k in _FIELDS:
                obj.setdefault(k, "")
            return obj
    except Exception:
        logger.exception("JSON parse failed for LLM translation output")
    return None


# --- concern refinement -----------------------------------------------------

def _generic_concern(language: str) -> str:
    if _is_kiswahili(language):
        return html.escape(
            "Muone daktari wako haraka kupanga hatua za matibabu. "
            "Nenda hospitali ikiwa una maumivu makali, homa, au dalili zinazoongezeka."
        )
    return html.escape(
        "See your doctor urgently to plan next steps for treatment. "
        "Go to hospital if you have severe pain, fever, or worsening symptoms."
    )


def _refine_concern(fields: Dict[str, str], language: str) -> str:
    """Call the LLM once more if the concern section came back too short."""
    system = ("You write short, patient-facing next-step advice. "
              "Use second person. Avoid identifiers. Write ONLY in {language}."
              ).replace("{language}", language or "English")
    if _is_kiswahili(language):
        system += " Andika kwa Kiswahili safi tu; usichanganye na Kiingereza. Tumia maneno rahisi ya kila siku."

    developer = (
        "Return ONLY the Note of Concern text: 2–3 short sentences (<= 300 characters total). "
        "Include urgent referrals, likely procedures, and clear red-flags (go to hospital if ...). "
        "No markdown. No quotes. No JSON."
    )
    if _is_kiswahili(language):
        developer += " LAZIMA kuwa Kiswahili tu; hakuna Kiingereza kabisa."

    user = (
        "Context from report (plain text):\n"
        f"Reason: {html.unescape(fields['reason'])}\n"
        f"Technique: {html.unescape(fields['technique'])}\n"
        f"Findings bullets: {re.sub(r'<[^>]+>', ' ', fields['findings'])}\n"
        f"Conclusion: {html.unescape(fields['conclusion'])}\n"
        f"Draft concern (may be incomplete): {html.unescape(fields['concern'])}\n"
        "Write the final Note of Concern now."
    )
    refined = _call_gpt5([
        {"role": "system", "content": system},
        {"role": "developer", "content": developer},
        {"role": "user", "content": user},
    ]).strip()
    return html.escape(refined) if refined else ""


# --- Kiswahili HTML re-translation pass --------------------------------------

def _enforce_kiswahili_html(fields: Dict[str, str]) -> Dict[str, str]:
    """Run Kiswahili dictionary translation against already-rendered HTML strings."""

    def text(s: str) -> str:
        return html.escape(_to_kiswahili(html.unescape(s))) if s else s

    def findings(body: str) -> str:
        if not body:
            return body
        if body.strip().lower().startswith("<ul"):
            def repl(m: re.Match) -> str:
                return f"<li>{html.escape(_to_kiswahili(html.unescape(m.group(1) or '')))}</li>"
            return re.sub(r"<li>(.*?)</li>", repl, body, flags=re.S | re.I)
        # Dash-text → rebuild UL
        lines = ["- " + _to_kiswahili(ln.strip()[2:])
                 for ln in body.splitlines() if ln.strip().startswith("- ")]
        return _dashes_to_ul("\n".join(lines) if lines else _to_kiswahili(body))

    return {
        "reason": text(fields["reason"]),
        "technique": text(fields["technique"]),
        "findings": findings(fields["findings"]),
        "conclusion": text(fields["conclusion"]),
        "concern": text(fields["concern"]),
    }


# --- Public entry -----------------------------------------------------------

def build_structured(
    report_text: str,
    glossary: Optional[Glossary] = None,
    *,
    language: str = "English",
) -> Dict[str, str]:
    """Build the structured patient-friendly summary consumed by result.html."""
    cleaned = _strip_html(report_text or "")

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

    raw = _gpt_with_retry(_compose_prompt(meta, secs, language))

    # ── No LLM output: fall back entirely to local heuristics ───────────
    if not raw:
        logger.warning("LLM output empty; using heuristic fallback")
        fields = _build_fallback(secs, language)
    else:
        parts = _parse_llm_output(raw)

        # Optional pure-Kiswahili re-translation pass on the structured parts
        if _is_kiswahili(language):
            try:
                translated = _translate_parts_via_llm(parts, language="Kiswahili")
                if translated:
                    parts = translated
            except Exception:
                logger.exception("LLM Kiswahili translation pass failed")

        fields = {
            "reason": html.escape(_as_text(parts.get("reason"))),
            "technique": html.escape(_as_text(parts.get("technique"))),
            "findings": _dashes_to_ul(_as_bullets_text(parts.get("findings"))),
            "conclusion": html.escape(_as_text(parts.get("conclusion"))),
            "concern": html.escape(_as_text(parts.get("concern"))),
        }

        # If concern is too short, attempt a focused refinement, then fall back generic
        if len(_strip_html(fields["concern"])) < 60:
            try:
                refined = _refine_concern(fields, language)
                if refined:
                    fields["concern"] = refined
            except Exception:
                logger.exception("Concern refinement call failed")

    # Backfill any empties from the raw extracted sections
    for key, src_key in (("reason", "reason"), ("technique", "technique"),
                         ("conclusion", "impression")):
        if not _strip_html(fields[key]):
            fields[key] = html.escape(" ".join(
                _simplify_then_translate(s, language) for s in _sentences(secs.get(src_key, ""), 2)
            ))
    if not _strip_html(fields["findings"]):
        bullets = [_simplify_then_translate(s, language)
                   for s in _sentences(secs.get("findings", ""), 4)]
        fields["findings"] = _dashes_to_ul("\n".join(f"- {s}" for s in bullets))
    if not _strip_html(fields["concern"]):
        fields["concern"] = _generic_concern(language)

    # Pure-Kiswahili enforcement on the rendered HTML strings (belt-and-braces)
    if _is_kiswahili(language):
        fields = _enforce_kiswahili_html(fields)

    patient = {
        "hospital": meta.get("hospital", ""),
        "study": meta.get("study", "Unknown"),
        "name": "",  # PHI stripped
        "sex": meta.get("sex", ""),
        "age": meta.get("age", ""),
        "date": meta.get("date", ""),
        "history": secs.get("reason", ""),
    }

    blob = " ".join(_strip_html(fields[k]) for k in _FIELDS)
    out: Dict[str, object] = {"patient": patient, **fields}
    out["word_count"] = len(blob.split())
    out["sentence_count"] = len(re.findall(r"[.!?]+", blob))

    logger.info(
        "summary_keys=%s",
        {k: len(_strip_html(fields[k])) for k in _FIELDS},
    )
    return out  # type: ignore[return-value]
