# src/translate.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List
import csv, re, os, json, logging

# ---------- logging ----------
logger = logging.getLogger("insideimaging")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------- parse import with safe fallbacks ----------
try:
    from .parse import parse_metadata, sections_from_text
except Exception:
    logger.warning("parse.py unavailable; using simple fallbacks")

    def parse_metadata(text: str) -> Dict[str, str]:
        return {"name": "", "age": "", "sex": "", "hospital": "", "date": "", "study": ""}

    def sections_from_text(text: str) -> Dict[str, str]:
        parts = {"reason": "", "technique": "", "findings": "", "impression": ""}
        blocks = re.split(r"\n\s*\n", text or "")
        whole = " ".join(b.strip() for b in blocks if b.strip())
        parts["findings"] = whole
        return parts

# ---------- helpers ----------
def _extract_json_loose(s: str) -> Dict[str, str] | None:
    if not s:
        return None
    try:
        return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, flags=re.S)
        if not m:
            return None
        try:
            return json.loads(m.group(0))
        except Exception:
            return None

def _summarize_with_openai(report_text: str, language: str) -> Dict[str, str] | None:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        return None
    try:
        # Prefer Responses API if available
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            model = os.getenv("OPENAI_MODEL", "gpt-5")
            instructions = (
                    "You are a medical report summarizer for the public. "
                    f"Write all output in {language}. "
                    "Return ONLY a JSON object with keys: reason, technique, findings, conclusion, concern. "
                    "Write for a 12-year-old. One or two short sentences per field. Plain words. No jargon. No treatment advice. "
                    "In findings and conclusion, wrap important phrases with **double asterisks**. "
                    "For GOOD news use words like: normal, no problem, no sign of, benign, stable, improved. "
                    "For BAD news use words like: mass, tumor, cancer, bleed, fracture, obstruction, perforation, ischemia, rupture, lesion. "
                    "Keep numbers simple and rounded. No extra keys or text outside the JSON."
            )
            resp = client.responses.create(
                model=model,
                instructions=instructions,
                input=[{"role": "user", "content": report_text}],
                max_output_tokens=1200,
            )
            text = getattr(resp, "output_text", None) or str(resp)
            data = _extract_json_loose(text) or {}
        except Exception:
            # Fallback to Chat Completions signature
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            model = os.getenv("OPENAI_MODEL", "gpt-5")
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content":  "Return JSON only with keys {reason, technique, findings, conclusion, concern}. "
                    "Write for a 12-year-old. One or two short sentences per field. Plain words. No jargon. No treatment advice. "
                    "In findings and conclusion, wrap important phrases with **double asterisks**. "
                    "Use words like 'normal/no/benign/stable/improved' for good news and "
                    "'mass/tumor/cancer/bleed/fracture/obstruction/perforation/ischemia/rupture/lesion' for bad news. "
                    "Keep numbers simple. No extra text."},
                    {"role": "user", "content": report_text},
                ],
                max_tokens=800,
            )
            data = _extract_json_loose(resp.choices[0].message.content) or {}

        out = {}
        for k in ("reason", "technique", "findings", "conclusion", "concern"):
            v = data.get(k, "")
            out[k] = v.strip() if isinstance(v, str) else str(v or "")
        return out
    except Exception:
        logger.exception("[LLM] summarization failed")
        return None

# ---------- glossary ----------
@dataclass
class Glossary:
    mapping: Dict[str, str]

    @classmethod
    def load(cls, path: str) -> "Glossary":
        m: Dict[str, str] = {}
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                rdr = csv.reader(f)
                for row in rdr:
                    if len(row) >= 2:
                        k = (row[0] or "").strip().lower()
                        v = (row[1] or "").strip()
                        if k:
                            m[k] = v
        except Exception:
            logger.exception("glossary load failed")
        return cls(m)

    def replace_terms(self, text: str) -> str:
        if not text:
            return ""
        out = text
        for k, v in self.mapping.items():
            out = re.sub(rf"\b{re.escape(k)}\b", v, out, flags=re.I)
        return out

def _simplify(text: str, lay_gloss: Glossary | None) -> str:
    if not text:
        return ""
    out = text
    if lay_gloss:
        out = lay_gloss.replace_terms(out)
    out = re.sub(r"\bcm\b", " centimeters", out, flags=re.I)
    out = re.sub(r"\bmm\b", " millimeters", out, flags=re.I)
    out = re.sub(r"\bHU\b", " Hounsfield units", out, flags=re.I)
    return out.strip()

def _convert_highlights(htmlish: str) -> str:
    if not htmlish:
        return ""
    NEG = ["mass", "obstruction", "compression", "invasion", "perforation", "ischemia", "tumor", "cancer", "lesion", "bleed", "rupture"]
    POS = ["normal", "benign", "unremarkable", "no ", "none", "stable", "improved"]
    def classify(m: re.Match) -> str:
        txt = m.group(1)
        low = txt.lower()
        cls = "negative" if any(k in low for k in NEG) else "positive" if any(k in low for k in POS) else "positive"
        return f'<strong class="{cls}">{txt}</strong>'
    return re.sub(r"\*\*(.*?)\*\*", classify, htmlish)

# ---------- single canonical API ----------
def build_structured(text: str, lay_gloss: Glossary | None = None, language: str = "English") -> Dict[str, str]:
    meta = parse_metadata(text or "")
    secs = sections_from_text(text or "")

    reason = secs.get("reason") or "Not provided."
    technique = secs.get("technique") or "Not provided."
    findings_src = secs.get("findings") or (text or "Not described.")
    impression_src = secs.get("impression") or ""

    # pull simple fields if present (line-anchored)
    m = re.search(r"(?mi)^\s*comparison\s*:\s*(.+)$", text or "")
    comparison = (m.group(1).strip() if m else "")
    m = re.search(r"(?mi)^\s*oral\s+contrast\s*:\s*(.+)$", text or "")
    oral_contrast = (m.group(1).strip() if m else "")

    # Try LLM
    llm = _summarize_with_openai(text or "", language)
    if llm:
        reason = llm.get("reason") or reason
        technique = llm.get("technique") or technique
        findings = llm.get("findings") or ""
        conclusion = llm.get("conclusion") or ""
        concern = llm.get("concern") or ""
    else:
        findings = _simplify(findings_src, lay_gloss)
        base_conc = impression_src or ""
        if not base_conc:
            picks: List[str] = []
            for kw in ["mass", "obstruction", "compression", "dilation", "fracture", "bleed", "appendicitis"]:
                m = re.search(rf"(?is)([^.]*\b{kw}\b[^.]*)\.", text or "")
                if m:
                    picks.append(m.group(0).strip())
            base_conc = " ".join(dict.fromkeys(picks))
        conclusion = _simplify(base_conc or "See important findings.", lay_gloss)
        concern = ""
        for kw in ["obstruction", "compression", "invasion", "perforation", "ischemia"]:
            if re.search(rf"(?i)\b{kw}\b", text or ""):
                concern = f"The findings include {kw}. Discuss next steps with your clinician."
                break

    findings = _convert_highlights(findings)
    conclusion = _convert_highlights(conclusion)

    # simple stats (optional for UI)
    words = len(re.findall(r"\w+", text or ""))
    sentences = len(re.findall(r"[.!?]+", text or ""))
    pos_hi = findings.count('class="positive"') + conclusion.count('class="positive"')
    neg_hi = findings.count('class="negative"') + conclusion.count('class="negative"')

    return {
        "name": meta.get("name", ""),
        "age": meta.get("age", ""),
        "sex": meta.get("sex", ""),
        "hospital": meta.get("hospital", ""),
        "date": meta.get("date", ""),
        "study": meta.get("study", ""),
        "reason": reason.strip(),
        "technique": technique.strip(),
        "comparison": comparison,
        "oral_contrast": oral_contrast,
        "findings": findings.strip(),
        "conclusion": conclusion.strip(),
        "concern": concern.strip(),
        "word_count": words,
        "sentence_count": sentences,
        "highlights_positive": pos_hi,
        "highlights_negative": neg_hi,
    }

__all__ = ["Glossary", "build_structured"]
