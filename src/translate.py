# src/translate.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List
import csv, re, os, json, logging, html as _html

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
                    {
                        "role": "system",
                        "content":
                            "Return JSON only with keys {reason, technique, findings, conclusion, concern}. "
                            "Write for a 12-year-old. One or two short sentences per field. Plain words. No jargon. No treatment advice. "
                            "In findings and conclusion, wrap important phrases with **double asterisks**. "
                            "Use words like 'normal/no/benign/stable/improved' for good news and "
                            "'mass/tumor/cancer/bleed/fracture/obstruction/perforation/ischemia/rupture/lesion' for bad news. "
                            "Keep numbers simple. No extra text."
                    },
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

# --- simple language + auto-highlighting ---
POS_WORDS = ["normal", "benign", "unremarkable", "no ", "none", "clear", "symmetric", "intact", "not enlarged", "stable", "improved"]
NEG_WORDS = ["mass", "tumor", "cancer", "lesion", "adenopathy", "enlarged", "necrotic", "metastasis", "obstruction", "compression", "invasion", "perforation", "ischemia", "fracture", "bleed", "hydroureteronephrosis"]

# Definitions for red terms (tooltips)
NEG_DEFS: Dict[str, str] = {
    "mass": "an abnormal lump",
    "tumor": "a growth that forms a lump",
    "cancer": "a harmful growth that can spread",
    "lesion": "an abnormal spot or area",
    "adenopathy": "swollen lymph nodes",
    "enlarged": "bigger than normal",
    "necrotic": "dead tissue",
    "metastasis": "spread to other areas",
    "obstruction": "a blockage",
    "compression": "being pressed",
    "invasion": "growing into nearby tissues",
    "perforation": "a hole or tear",
    "ischemia": "low blood flow",
    "fracture": "a broken bone",
    "bleed": "bleeding",
    "hydroureteronephrosis": "swelling of kidney and ureter from blockage",
}

_SIMPLE_MAP = [
    (r"\bunremarkable\b", "looks normal"),
    (r"\bintact\b", "normal"),
    (r"\bsymmetric\b", "same on both sides"),
    (r"\bbenign\b", "not dangerous"),
    (r"\badenopathy\b", "swollen lymph nodes"),
    (r"\bnecrotic\b", "dead tissue"),
    (r"\bmetastasis\b", "spread to other areas"),
    (r"\binvasion\b", "growing into nearby tissues"),
    (r"\bobstruction\b", "blockage"),
    (r"\bcompression\b", "being pressed"),
    (r"\bperforation\b", "a hole/tear"),
    (r"\bischemia\b", "low blood flow"),
    (r"\bdilation\b", "widening"),
    (r"\bextra[-\s]?axial\b", "outside the brain surface"),
]

_ANATOMY_EXPLAIN = [
    (r"\bnasopharynx\b", "nasopharynx (back of the nose)"),
    (r"\blarynx\b", "larynx (voice box)"),
    (r"\bpalatine tonsils\b", "tonsils"),
    (r"\blingual tonsils?\b", "tonsil tissue at the base of the tongue"),
    (r"\bparanasal sinuses\b", "sinuses (air pockets in the face)"),
    (r"\bcraniocervical junction\b", "where the skull meets the neck"),
    (r"\bparotid\b", "parotid gland (saliva gland in front of the ear)"),
    (r"\bsubmandibular\b", "submandibular gland (saliva gland under the jaw)"),
    (r"\bcarotid\b", "carotid artery (large neck artery)"),
    (r"\bjugular\b", "jugular vein (large neck vein)"),
    (r"\bthyroid\b", "thyroid gland"),
    (r"\bfronto[-\s]?parietal\b", "front-top area of the brain"),
    (r"\bsphenoid wing\b", "bone near the temple"),
    (r"\bmeninges\b", "the brain’s lining"),
    (r"\bsubfalcine herniation\b", "pressure pushing brain tissue under the middle fold"),
    (r"\bperilesional edema\b", "swelling around the spot"),
    (r"\bmeningioma\b", "meningioma (a tumor from the brain’s lining)"),
]

# Clickable organ tokens -> data-organ keys
_ORGAN_MAP: Dict[str, str] = {
    "cervical spine": "cervical-spine",
    "lumbar spine": "lumbar-spine",
    "thoracic spine": "thoracic-spine",
    "head": "head",
    "brain": "head",
    "neck": "neck",
    "chest": "chest",
    "abdomen": "abdomen",
    "belly": "abdomen",
    "pelvis": "pelvis",
    "heart": "heart",
    "lung": "lung",
    "liver": "liver",
    "kidney": "kidney",
    "spleen": "spleen",
    "pancreas": "pancreas",
    "bladder": "bladder",
    "prostate": "prostate",
    "ovary": "ovary",
    "uterus": "uterus",
}

# precompile organ regex (longest first to avoid partial overlaps)
_org_keys_sorted = sorted(_ORGAN_MAP.keys(), key=len, reverse=True)
_ORG_RX = re.compile(r"(?i)\b(" + "|".join(re.escape(k) for k in _org_keys_sorted) + r")\b")

def _link_organs(s: str) -> str:
    """Wrap organ/body terms with a clickable span."""
    if not s:
        return ""
    def _rep(m: re.Match) -> str:
        text = m.group(0)
        key = _ORGAN_MAP.get(text.lower(), text.lower())
        return f'<span class="organ-link" data-organ="{_html.escape(key)}">{_html.escape(text)}</span>'
    return _ORG_RX.sub(_rep, s)

def _simplify_language(s: str) -> str:
    if not s:
        return ""
    out = s
    for pat, repl in _SIMPLE_MAP:
        out = re.sub(pat, repl, out, flags=re.I)
    return out

def _explain_anatomy(s: str) -> str:
    if not s:
        return ""
    out = s
    for pat, repl in _ANATOMY_EXPLAIN:
        out = re.sub(pat, repl, out, flags=re.I)
    return out

def _mark_highlights(s: str) -> str:
    if not s:
        return ""
    out = s
    for w in POS_WORDS:
        if w.endswith(" "):  # e.g., "no "
            out = re.sub(rf"(?i)(?<!\w){re.escape(w.strip())}\s+\w+", lambda m: f"**{m.group(0)}**", out)
        else:
            out = re.sub(rf"(?i)\b{re.escape(w)}\b", lambda m: f"**{m.group(0)}**", out)
    for w in NEG_WORDS:
        out = re.sub(rf"(?i)\b{re.escape(w)}\b", lambda m: f"**{m.group(0)}**", out)
    return out

def _numbers_simple(s: str) -> str:
    # round plain numbers
    def _round(m: re.Match) -> str:
        num = m.group(0)
        try:
            f = float(num)
            if abs(f) >= 10:
                return str(int(round(f)))
            return f"{round(f,1):g}"
        except Exception:
            return num
    s2 = re.sub(r"(?<!\w)(\d+\.\d+|\d+)(?!\w)", _round, s)
    # normalize multiplication sign ONLY between digits (e.g., 7x6 -> 7 x 6)
    s2 = re.sub(r"(?<=\d)\s*[x×]\s*(?=\d)", " x ", s2)
    return s2

def _split_sentences(s: str) -> List[str]:
    text = re.sub(r"\s+", " ", s or "").strip()
    if not text:
        return []
    return re.split(r"(?<=[.!?])\s+", text)

def _is_negative(low: str) -> bool:
    if any(k in low for k in ["no ", "without", " not "]):
        return False
    return any(w in low for w in NEG_WORDS)

def _is_positive(low: str) -> bool:
    return any(w in low for w in POS_WORDS) or any(k in low for k in ["no ", "without", " not "])

def _bullets_simpler(s: str, max_items: int = 6, keep_pos: int = 1) -> str:
    sentences = _split_sentences(s)
    neg_list: List[str] = []
    pos_list: List[str] = []
    for sent in sentences:
        t = _numbers_simple(_explain_anatomy(_simplify_language(sent.strip())))
        if re.match(r"(?i)^(conclusion|impression|ddx)[:\s]", t) or re.match(r"(?i)^dr\b", t):
            continue
        low = t.lower()
        if _is_negative(low):
            neg_list.append(_link_organs(t))  # add organ links before highlighting
        elif _is_positive(low):
            pos_list.append(_link_organs(t))

    # dedupe while keeping order
    seen = set()
    neg_list = [x for x in neg_list if not (x in seen or seen.add(x))]
    pos_list = [x for x in pos_list if not (x in seen or seen.add(x))]

    bullets: List[str] = []
    for t in neg_list[: max_items - 1]:
        bullets.append(_mark_highlights(t))

    if keep_pos > 0 and pos_list:
        bullets.append(_mark_highlights("Most other areas **look normal**."))
    if not bullets:
        bullets = [_mark_highlights("No major problems were seen.")]
    html = "<ul>" + "".join(f"<li>{b}</li>" for b in bullets[:max_items]) + "</ul>"
    return _convert_highlights(html)

def _clean_label_prefixes(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"(?im)^\s*(reason|indication|procedure|technique|findings|impression|conclusion|ddx)\s*:\s*", "", s).strip()

def _strip_section_headers(s: str) -> str:
    if not s:
        return ""
    # remove inline labels like "Conclusion:" or "DDX:" wherever they appear
    return re.sub(r"(?i)\b(findings?|impression|conclusion|ddx)\s*:\s*", "", s)

def _infer_modality_and_region(text: str) -> str:
    low = (text or "").lower()
    modality = None
    region = None
    with_contrast = False

    if "mri" in low:
        modality = "MRI"
    elif re.search(r"\bct\b", low):
        modality = "CT"
    elif "ultrasound" in low or "sonograph" in low:
        modality = "Ultrasound"
    elif re.search(r"x-?ray|radiograph", low):
        modality = "X-ray"

    if "contrast" in low:
        with_contrast = True

    if any(w in low for w in ["cervical spine", "c-spine"]):
        region = "cervical spine"
    elif any(w in low for w in ["lumbar spine", "l-spine", "lspine"]):
        region = "lumbar spine"
    elif "thoracic spine" in low:
        region = "thoracic spine"
    elif "neck" in low or "cervical" in low:
        region = "neck"
    elif "chest" in low or "thorax" in low or "lung" in low:
        region = "chest"
    elif "abdomen" in low or "abdominal" in low or "belly" in low:
        region = "abdomen"
    elif "pelvis" in low:
        region = "pelvis"
    elif "head" in low or "skull" in low or "brain" in low:
        region = "head"

    if modality:
        if region:
            if modality == "CT":
                return f"CT scan of the {region}" + (" with contrast." if with_contrast else ".")
            else:
                return f"{modality} of the {region}."
        else:
            if modality == "CT":
                return "CT scan" + (" with contrast." if with_contrast else ".")
            else:
                return f"{modality}."
    return ""

def _infer_reason(text: str, seed: str) -> str:
    src = seed or ""
    if not src:
        m = re.search(r"(?im)^\s*(indication|reason|history)\s*:\s*(.+)$", text or "")
        if m:
            src = m.group(2).strip()

    s = _simplify_language(src)
    s = _numbers_simple(s)
    s = re.sub(r"\bintra[- ]abdominal\b", "belly", s, flags=re.I)
    s = re.sub(r"\bcervical\b", "neck", s, flags=re.I)
    s = re.sub(r"\b\?\s*", "possible ", s)

    want_lymph = bool(re.search(r"\blymphoma\b", s, flags=re.I))
    want_mass = bool(re.search(r"\bmass\b", s, flags=re.I) or re.search(r"\badenopathy\b", s, flags=re.I))
    parts: List[str] = []
    if want_mass:
        parts.append("The scan was done to check for a **mass** and **swollen lymph nodes**.")
    else:
        parts.append("The scan was done to look for a problem in the neck.")
    if want_lymph:
        parts.append("Doctors wanted to see if there were signs of **lymphoma** (a blood cancer).")
    else:
        parts.append("Doctors wanted to find the cause of the symptoms.")
    return " ".join(parts)

def _convert_highlights(htmlish: str) -> str:
    if not htmlish:
        return ""
    NEG = [
        "mass","obstruction","compression","invasion","perforation","ischemia",
        "tumor","cancer","lesion","bleed","rupture","fracture",
        "adenopathy","enlarged","necrotic","metastasis","hydroureteronephrosis"
    ]
    POS = [
        "normal","benign","unremarkable","no ","none","stable","improved",
        "clear","symmetric","intact","not enlarged","without"
    ]
    def classify(m: re.Match) -> str:
        txt = m.group(1)
        low = txt.lower()
        is_positive = any(p in low for p in ["no ", "without", " not "]) or any(p in low for p in POS)
        is_negative = any(k in low for k in NEG)
        if is_positive and not is_negative:
            return f'<strong class="positive">{_html.escape(txt)}</strong>'
        if is_negative and not is_positive:
            # pick first matching negative token for definition
            term = next((w for w in NEG_WORDS if w in low), None)
            definition = NEG_DEFS.get(term or "", "")
            data_attr = f' data-def="{_html.escape(definition)}"' if definition else ""
            return f'<strong class="negative"{data_attr}>{_html.escape(txt)}</strong>'
        # If both detected, prefer positive due to context like "no mass"
        if is_positive:
            return f'<strong class="positive">{_html.escape(txt)}</strong>'
        # default
        return f'<strong class="positive">{_html.escape(txt)}</strong>'
    # Replace **...** with <strong> preserving nested occurrences
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

    # local fallbacks
    fallback_findings = _simplify(findings_src, lay_gloss)
    base_conc = impression_src or ""
    if not base_conc:
        picks: List[str] = []
        for kw in ["mass", "obstruction", "compression", "dilation", "fracture", "bleed", "appendicitis", "adenopathy", "necrotic"]:
            m2 = re.search(rf"(?is)([^.]*\b{kw}\b[^.]*)\.", text or "")
            if m2:
                picks.append(m2.group(0).strip())
        base_conc = " ".join(dict.fromkeys(picks))
    fallback_conclusion = _simplify(base_conc or "See important findings.", lay_gloss)
    concern = ""
    for kw in ["obstruction", "compression", "invasion", "perforation", "ischemia"]:
        if re.search(rf"(?i)\b{kw}\b", text or ""):
            concern = f"The findings include {kw}. Discuss next steps with your clinician."
            break

    # Try LLM and merge
    llm = _summarize_with_openai(text or "", language)
    if llm:
        llm_reason = _clean_label_prefixes(llm.get("reason", ""))
        llm_tech = _clean_label_prefixes(llm.get("technique", ""))
        inferred_reason = _infer_reason(text or "", llm_reason or reason)
        inferred_tech = _infer_modality_and_region(text or "")
        reason = inferred_reason or llm_reason or reason
        technique = inferred_tech or llm_tech or technique

        raw_findings = llm.get("findings", "").strip() or fallback_findings
        raw_conclusion = llm.get("conclusion", "").strip() or fallback_conclusion
        concern = llm.get("concern", "").strip() or concern
    else:
        reason = _infer_reason(text or "", reason)
        technique = _infer_modality_and_region(text or "") or technique
        raw_findings = fallback_findings
        raw_conclusion = fallback_conclusion

    # strip any embedded section labels before simplification
    raw_findings = _strip_section_headers(_clean_label_prefixes(raw_findings))
    raw_conclusion = _strip_section_headers(_clean_label_prefixes(raw_conclusion))

    # simplify, explain anatomy, link organs, auto-highlight, compress to bullets
    findings = _bullets_simpler(raw_findings, max_items=6, keep_pos=1)
    conclusion = _bullets_simpler(raw_conclusion, max_items=4, keep_pos=0)

    # Reason/technique: add organ links and allow inline emphasis if present
    reason_html = _link_organs(reason)
    technique_html = _link_organs(technique)
    concern_html = _link_organs(concern) if concern else concern

    # simple stats
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
        "reason": reason_html.strip(),
        "technique": technique_html.strip(),
        "comparison": comparison,
        "oral_contrast": oral_contrast,
        "findings": findings.strip(),
        "conclusion": conclusion.strip(),
        "concern": concern_html.strip(),
        "word_count": words,
        "sentence_count": sentences,
        "highlights_positive": pos_hi,
        "highlights_negative": neg_hi,
    }

__all__ = ["Glossary", "build_structured"]
