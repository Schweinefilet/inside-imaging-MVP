"""Glossary-based simplification and structured report building.

This module defines a Glossary class for term replacement using CSV files,
functions to simplify raw report text into plainer language, and a function
that constructs a structured dictionary containing sections suitable for
displaying in the user interface. It depends on parse.py for extracting
metadata and sections.

This version also supports optional OpenAI integration for deeper lay
summarisation. When configured via the ``OPENAI_API_KEY`` environment
variable, the module will send the raw report to an OpenAI model and
request a JSON summary. To allow for more thorough reasoning, the call
enforces a minimum wall-clock time (defaults to 30 seconds, adjustable
via ``OPENAI_THINK_MIN`` or ``OPENAI_THINK_TIME``). If OpenAI is
unavailable or returns an error, the code falls back to glossary-based
simplification. All timings and failures are logged to the ``insideimaging``
logger to aid debugging.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List
import csv
import re
import os
import json
import time
import logging

from .parse import parse_metadata, sections_from_text

# ---------------------------------------------------------------------------
# Logging configuration
# Use the 'insideimaging' logger defined in app.py. If the application has
# not configured logging, default to logging to stderr.
logger = logging.getLogger("insideimaging")
if not logger.handlers:
    # Fallback basic configuration so that debug output is visible when
    # running this module directly.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def _env_float(name: str, default: float) -> float:
    """Parse a floating-point environment variable, returning a default on error."""
    try:
        return float(os.getenv(name, str(default)))
    except Exception:
        return default


def _min_think_seconds() -> float:
    """Return minimum wall-clock think time (seconds) for OpenAI calls."""
    v = os.getenv("OPENAI_THINK_MIN") or os.getenv("OPENAI_THINK_TIME")
    try:
        return float(v) if v else 30.0
    except Exception:
        return 30.0


def _extract_json_loose(s: str) -> Dict[str, str] | None:
    """Parse JSON from a string, even if it contains extraneous text or code fences."""
    try:
        return json.loads(s)
    except Exception:
        # Extract the first JSON object
        m = re.search(r"\{.*\}", s, flags=re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None


def _responses_api_client():
    """Return a configured OpenAI Responses API client or None if not available."""
    try:
        from openai import OpenAI  # type: ignore
    except Exception:
        return None
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    timeout = _env_float("OPENAI_TIMEOUT", 60.0)
    try:
        return OpenAI(api_key=api_key, timeout=timeout)
    except TypeError:
        # Older versions may not accept 'timeout'
        return OpenAI(api_key=api_key)


def _chat_api_available() -> bool:
    """Return True if the legacy ChatCompletion API is importable."""
    try:
        import openai  # type: ignore
        return True
    except Exception:
        return False




def _extract_json_loose(text: str):
    if not text: return None
    try:
        return json.loads(text)
    except Exception:
        pass
    m = re.search(r'(\{.*\})', text, flags=re.S)
    if m:
        try: return json.loads(m.group(1))
        except Exception: pass
    return None

def _summarize_with_openai(report_text: str, language: str) -> Dict[str, str] | None:
    """Summarize using OpenAI; enforce min think time and highlight phrases."""
    import time
    instructions = (
        "You are a medical report summarizer for the public. "
        f"Write all output in {language}. "
        "Return ONLY a JSON object with keys: reason, technique, findings, conclusion, concern. "
        "Use clear, simple language and short sentences. No treatment advice. "
        "Highlight important phrases by wrapping them in **double asterisks** in findings and conclusion."
    )

    min_think = _min_think_seconds()
    max_out   = int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS", "2048"))
    model_responses = os.getenv("OPENAI_MODEL", "gpt-5")
    model_chat = os.getenv("OPENAI_MODEL", "gpt-5")

    # ---- Try Responses API (v1) ----
    client = _responses_api_client()
    if client is not None:
        try:
            t_start = time.perf_counter()
            logger.info("[LLM] Responses.create model=%s", model_responses)
            resp = client.responses.create(
                model=model_responses,
                instructions=instructions,
                input=[{"role": "user", "content": report_text}],
                reasoning={"effort": "high"},
                max_output_tokens=max_out
            )
            elapsed = time.perf_counter() - t_start
            if elapsed < min_think:
                time.sleep(min_think - elapsed)
            print(f"[LLM] think time {elapsed:.2f}s; enforced >= {min_think:.2f}s")
            logger.info("[LLM] Responses finished in %.2fs; enforced >= %.2fs", elapsed, min_think)

            # Try to extract text robustly across SDK variants
            text = getattr(resp, "output_text", None)
            if not text:
                try:
                    text = resp.output[0].content[0].text
                except Exception:
                    text = str(resp)
            data = _extract_json_loose(text) or {}
            for k in ("reason","technique","findings","conclusion","concern"):
                data.setdefault(k, "")
            return {
                "reason": data["reason"].strip(),
                "technique": data["technique"].strip(),
                "findings": data["findings"].strip(),
                "conclusion": data["conclusion"].strip(),
                "concern": data["concern"].strip(),
            }
        except Exception:
            logger.exception("[LLM] Responses API failed")

    # ---- Fallback: Chat Completions (v1) ----
    try:
        from openai import OpenAI
        t_start = time.perf_counter()
        logger.info("[LLM] Chat Completions.create model=%s", model_chat)
        client2 = OpenAI(timeout=_env_float("OPENAI_TIMEOUT", 60.0))
        resp = client2.chat.completions.create(
            model=model_chat,
            messages=[
                {"role": "system", "content": instructions},
                {"role": "user", "content": report_text}
            ],
            max_tokens=800
        )
        elapsed = time.perf_counter() - t_start
        if elapsed < min_think:
            time.sleep(min_think - elapsed)
        print(f"[LLM] think time {elapsed:.2f}s; enforced >= {min_think:.2f}s")
        logger.info("[LLM] ChatCompletion finished in %.2fs; enforced >= %.2fs", elapsed, min_think)

        content = resp.choices[0].message.content
        data = _extract_json_loose(content) or {}
        for k in ("reason","technique","findings","conclusion","concern"):
            data.setdefault(k, "")
        return {
            "reason": data["reason"].strip(),
            "technique": data["technique"].strip(),
            "findings": data["findings"].strip(),
            "conclusion": data["conclusion"].strip(),
            "concern": data["concern"].strip(),
        }
    except Exception:
        logger.exception("[LLM] ChatCompletion failed")

    return None


def simplify_to_layman(text: str, lay_gloss: Glossary) -> str:
    """Simplify a block of report text using the lay glossary.

    Performs glossary replacement and also expands common medical abbreviations
    like cm â†’ centimeters and HU â†’ Hounsfield units. Returns the simplified
    string.
    """
    if not text.strip():
        return ""
    out = lay_gloss.replace_terms(text)
    out = re.sub(r"\bcm\b", " centimeters", out, flags=re.IGNORECASE)
    out = re.sub(r"\bmm\b", " millimeters", out, flags=re.IGNORECASE)
    out = re.sub(r"\bHU\b", " Hounsfield units", out, flags=re.IGNORECASE)
    return out.strip()

def build_structured(text: str, lay_gloss: Glossary, language: str = "English") -> Dict[str, str]:
    """Build a structured representation of a report with simplified sections.

    This function extracts metadata and report sections, then attempts to
    simplify the findings and conclusion using a glossary or an external
    language model if an API key is provided. The caller can specify a
    target language; if translation into the chosen language is desired,
    pass a non-English language. When no external API is configured,
    heuristic simplification using the glossary is performed.
    Returns a dictionary containing both patient fields and narrative
    sections.
    """
    meta = parse_metadata(text)
    secs = sections_from_text(text)
    # Reason for scan and technique
    reason = secs.get('reason') or "Not provided."
    technique = secs.get('technique') or "Not provided."
    # Source texts
    findings_source = secs.get('findings') or "Not described."
    impression_source = secs.get('impression')
    if not impression_source:
        # heuristically pull sentences with key words as a pseudo-conclusion
        picks: List[str] = []
        for kw in ["mass", "obstruction", "compression", "dilation", "fracture", "bleed", "appendicitis"]:
            m = re.search(rf"(?is)([^.]*\b{kw}\b[^.]*)\.", text)
            if m:
                picks.append(m.group(0).strip())
        impression_source = " ".join(dict.fromkeys(picks)) or "See important findings."

    # Attempt to use the LLM for deeper simplification
    simplified_findings: str | None = None
    simplified_conclusion: str | None = None
    concern = ""
    # First try OpenAI summarisation if configured
    llm_out = _summarize_with_openai(text, language)
    if llm_out:
        reason = llm_out.get("reason", reason) or reason
        technique = llm_out.get("technique", technique) or technique
        simplified_findings = llm_out.get("findings", "").strip() or None
        simplified_conclusion = llm_out.get("conclusion", "").strip() or None
        concern = llm_out.get("concern", "") or ""

    # Fallback to glossary simplification if necessary
    if simplified_findings is None:
        simplified_findings = simplify_to_layman(findings_source, lay_gloss)
    if simplified_conclusion is None:
        simplified_conclusion = simplify_to_layman(impression_source, lay_gloss)
    # If no explicit concern provided, derive heuristic note of concern
    if not concern:
        for kw in ["obstruction", "compression", "invasion", "perforation", "ischemia"]:
            if re.search(rf"(?i)\b{kw}\b", text):
                concern = f"The findings include {kw}. Discuss next steps with your clinician."
                break
    # Convert Markdown-style highlights (**word**) into <strong> tags with positive/negative classes.
    NEGATIVE_KEYWORDS = [
        "mass", "obstruction", "compression", "invasion", "perforation", "ischemia", "tumor",
        "cancer", "lesion", "bleed", "rupture"
    ]
    POSITIVE_KEYWORDS = [
        "normal", "benign", "unremarkable", "no", "none", "stable", "improved"
    ]
    def classify(match: re.Match) -> str:
        content = match.group(1)
        lower = content.lower()
        cls = "positive"
        # check if any negative keyword appears
        if any(kw in lower for kw in NEGATIVE_KEYWORDS):
            cls = "negative"
        elif any(kw in lower for kw in POSITIVE_KEYWORDS):
            cls = "positive"
        return f"<strong class=\"{cls}\">{content}</strong>"
    def convert_highlights(s: str) -> str:
        return re.sub(r"\*\*(.*?)\*\*", classify, s)

    simplified_findings = convert_highlights(simplified_findings)
    simplified_conclusion = convert_highlights(simplified_conclusion)

    return {
        "name": meta.get("name", ""),
        "age": meta.get("age", ""),
        "sex": meta.get("sex", ""),
        "hospital": meta.get("hospital", ""),
        "date": meta.get("date", ""),
        "study": meta.get("study", ""),
        "reason": reason,
        "technique": technique,
        "findings": simplified_findings,
        "conclusion": simplified_conclusion,
        "concern": concern,
    }




# --- begin fallback symbols (append) ---
from dataclasses import dataclass
from typing import Dict

@dataclass
class Glossary:
    mapping: Dict[str,str]
    @classmethod
    def load(cls, path: str) -> "Glossary":
        try:
            import csv
            m = {}
            with open(path, newline="", encoding="utf-8-sig") as f:
                rdr = csv.reader(f)
                for row in rdr:
                    if len(row) >= 2:
                        k = (row[0] or "").strip().lower()
                        v = (row[1] or "").strip()
                        if k: m[k] = v
            return cls(m)
        except Exception:
            return cls({})

def build_structured(report_text: str, language: str = "English") -> Dict[str,str]:
    # Try LLM path
    s = _summarize_with_openai(report_text, language)
    if not s:
        # very simple fallback
        s = {
            "reason": "",
            "technique": "",
            "findings": report_text.strip(),
            "conclusion": "",
            "concern": "",
        }
    # normalize keys
    for k in ("reason","technique","findings","conclusion","concern"):
        s.setdefault(k, "")
        if not isinstance(s[k], str): s[k] = str(s[k] or "")
    return s
# --- end fallback symbols ---

# --- canonical build_structured (appended last) ---
def build_structured(report_text: str,
                     glossary: "Glossary"|None = None,
                     language: str = "English") -> Dict[str, str]:
    """
    Summarize a report for lay readers. Uses LLM first; simple fallback otherwise.
    """
    res = _summarize_with_openai(report_text, language)
    if not res:
        res = {
            "reason": "",
            "technique": "",
            "findings": (report_text or "").strip(),
            "conclusion": "",
            "concern": "",
        }
    for k in ("reason","technique","findings","conclusion","concern"):
        v = res.get(k, "")
        res[k] = v if isinstance(v, str) else str(v or "")
    return res
# --- end canonical ---
