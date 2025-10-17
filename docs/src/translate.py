# src/translate.py
from __future__ import annotations

import csv, re, os, json, logging, time
from dataclasses import dataclass
from typing import Dict, List, Tuple
from openai import BadRequestError, NotFoundError
import ast

# ---------- logging ----------
logger = logging.getLogger("insideimaging")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---------- parse import with safe fallbacks ----------
try:
    from .parse import parse_metadata, sections_from_text
except Exception:
    logger.warning("parse.py unavailable; using robust fallbacks")

    def parse_metadata(text: str) -> Dict[str, str]:
        t = text or ""
        def grab(rx, default=""):
            m = re.search(rx, t, flags=re.I | re.M)
            return (m.group(1).strip() if m else default)
        name = grab(r"^\s*NAME\s*:\s*([^\n]+)")
        age = grab(r"^\s*AGE\s*:\s*([0-9]{1,3})")
        sex_raw = grab(r"^\s*SEX\s*:\s*([MF]|Male|Female)")
        sex = {"m":"M","f":"F","male":"M","female":"F"}.get(sex_raw.lower(), sex_raw) if sex_raw else ""
        date = grab(r"^\s*DATE\s*:\s*([0-9]{1,2}[/-][0-9]{1,2}[/-][0-9]{2,4})")
        study = grab(r"^\s*((?:MRI|CT|X-?RAY|ULTRASOUND|USG)[^\n]*)")
        hospital = grab(r"^[^\n]*HOSPITAL[^\n]*$")
        return {"name": name, "age": age, "sex": sex, "hospital": hospital, "date": date, "study": study}

    def sections_from_text(text: str) -> Dict[str, str]:
        t = (text or "")
        pat = re.compile(
            r"(?im)^\s*(clinical\s*history|history|indication|reason|technique|procedure(?:\s+and\s+findings)?|findings?|impression|conclusion|summary)\s*:\s*"
        )
        parts: Dict[str, str] = {"reason":"", "technique":"", "findings":"", "impression":""}
        hits = [(m.group(1).lower(), m.start(), m.end()) for m in pat.finditer(t)]
        if not hits:
            return parts | {"findings": t.strip()}
        hits.append(("__END__", len(t), len(t)))
        for i in range(len(hits)-1):
            label, _, end = hits[i]
            next_start = hits[i+1][1]
            body = t[end:next_start].strip()
            if not body:
                continue
            if label in ("clinical history","history","indication","reason"):
                parts["reason"] = (parts["reason"] + " " + body).strip()
            elif label.startswith("technique"):
                parts["technique"] = (parts["technique"] + " " + body).strip()
            elif label.startswith("procedure") or label.startswith("finding"):
                parts["findings"] = (parts["findings"] + " " + body).strip()
            elif label in ("impression","conclusion","summary"):
                parts["impression"] = (parts["impression"] + " " + body).strip()
        return {k:v.strip() for k,v in parts.items()}

# ---------- glossary ----------
@dataclass
class Glossary:
    mapping: Dict[str, str]
    @classmethod
    def load(cls, path: str) -> "Glossary":
        m: Dict[str, str] = {}
        try:
            with open(path, newline="", encoding="utf-8-sig") as f:
                for row in csv.reader(f):
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

# ---------- vocab ----------
POS_WORDS = ["normal","benign","unremarkable","clear","symmetric","intact","stable","improved","no ","without "]
NEG_WORDS = [
    "mass","tumor","cancer","lesion","adenopathy","enlarged","necrotic","metastasis",
    "obstruction","compression","invasion","perforation","ischemia","fracture","bleed",
    "hydroureteronephrosis","hydroureter","hydronephrosis","herniation","shift","edema",
    "swelling","atrophy","stenosis","anomaly",
]
NEG_PHRASES = [r"mass\s+effect", r"subfalcine\s+herniation", r"midline\s+shift", r"perilesional\s+edema"]
NEG_DEFS: Dict[str, str] = {
    "mass":"an abnormal lump that can press on tissue","tumor":"a growth that forms a lump","cancer":"a harmful growth that can spread",
    "lesion":"an abnormal spot or area","adenopathy":"swollen lymph nodes","enlarged":"bigger than normal","necrotic":"dead tissue",
    "metastasis":"spread to other areas","obstruction":"a blockage","compression":"being pressed by something","invasion":"growing into nearby tissues",
    "perforation":"a hole or tear","ischemia":"low blood flow","fracture":"a broken bone","bleed":"bleeding","herniation":"disc material pushed out",
    "edema":"swelling","atrophy":"shrinking of tissue","stenosis":"narrowing","anomaly":"difference from typical anatomy",
    "mass effect":"pressure on brain structures","subfalcine herniation":"brain shifted under the central fold","midline shift":"brain pushed off center",
    "perilesional edema":"swelling around the lesion",
}

# ---------- plain-language rewrites ----------
_JARGON_MAP = [
    (re.compile(r"\bsubfalcine\s+herniation\b", re.I), "subfalcine herniation, brain shift under the central fold"),
    (re.compile(r"\bperilesional\b", re.I), "around the lesion"),
    (re.compile(r"\bparenchymal\b", re.I), "brain tissue"),
    (re.compile(r"\bavid(ly)?\s+enhanc(?:ing|ement)\b|\bavid(ly)?\s+enhacing\b", re.I), "enhances with contrast dye"),
    (re.compile(r"\bextra[-\s]?axial\b", re.I), "outside the brain tissue"),
    (re.compile(r"\beffaced?\b", re.I), "pressed"),
    (re.compile(r"\bdilated\b", re.I), "widened"),
    (re.compile(r"\bemerging\s+from\s+the\b", re.I), "near the"),
    (re.compile(r"\bedema\b", re.I), "swelling"),
    (re.compile(r"\buvimbe\b", re.I), "mass"),
    # spine
    (re.compile(r"\bhypolordosis\b", re.I), "reduced normal neck curve"),
    (re.compile(r"\blordosis\b", re.I), "inward spine curve"),
    (re.compile(r"\bkyphosis\b", re.I), "forward rounding of the spine"),
    (re.compile(r"\bdisc\s+herniation\b", re.I), "disc bulge"),
    (re.compile(r"\bprotrusion\b", re.I), "bulge"),
    (re.compile(r"\bcalvarium\b", re.I), "skull bones"),
    (re.compile(r"\bcervical\b", re.I), "neck"),
    (re.compile(r"\bforamina?\b", re.I), "nerve openings"),
    (re.compile(r"\buvunjaji\b", re.I), "fracture"),
]
def _rewrite_jargon(s: str) -> str:
    out = s or ""
    for rx, repl in _JARGON_MAP:
        out = rx.sub(repl, out)
    return out

# ---------- tooltips ----------
_TERM_DEFS = [
    {"pat": r"\bmeningioma\b", "def": "tumor from the brain’s lining"},
    {"pat": r"\bextra[-\s]?axial\b", "def": "outside brain tissue but inside skull"},
    {"pat": r"\bsubfalcine\s+herniation\b", "def": "brain pushed under central fold"},
    {"pat": r"\bmass\s+effect\b", "def": "pressure or shift caused by a mass"},
    {"pat": r"\bperilesional\s+edema\b", "def": "swelling around a lesion"},
    {"pat": r"\bgreater\s+sphenoid\s+wing\b", "def": "part of skull bone near the temple"},
    {"pat": r"\bventricle[s]?\b", "def": "fluid spaces inside the brain"},
    # spine
    {"pat": r"\bhypolordosis\b", "def": "reduced normal inward curve of the neck"},
    {"pat": r"\bdisc\s+herniation\b", "def": "disc material pushed out"},
    {"pat": r"\bforamina?\b", "def": "openings where nerves exit"},
    {"pat": r"\bspondylosis\b", "def": "spine wear and tear"},
    {"pat": r"\bosteophyte\b", "def": "bone spur"},
    {"pat": r"\bcalvarium\b", "def": "skull bones over the brain"},
    {"pat": r"\buvunjaji\b", "def": "fracture"},
]
_TERM_REGEX: List[Tuple[re.Pattern, str]] = [(re.compile(d["pat"], re.I), d["def"]) for d in _TERM_DEFS]

# ---------- noise ----------
NOISE_PATTERNS = [
    r"\baxial\b", r"\bNECT\b", r"\bCECT\b", r"\bbrain window\b",
    r"\bimages?\s+are\s+viewed", r"\bappear\s+normal\b", r"\bare\s+normal\b",
    r"\bno\s+abnormalit(y|ies)\b", r"\bnormally\s+developed\b",
    r"\bparanasal\s+sinuses.*(clear|pneumatiz)", r"\bvisuali[sz]ed\s+lower\s+thorax\s+is\s+normal",
    r"^\s*(conclusion|impression|summary)\s*:\s*",
]
NOISE_RX = re.compile("|".join(f"(?:{p})" for p in NOISE_PATTERNS), re.I | re.M)

# ---------- PHI redaction ----------
def _redact_phi(s: str) -> str:
    t = s or ""
    t = re.sub(r"(?im)^\s*(name|patient|pt|mrn|id|acct|account|gender|sex|age|dob|date\s+of\s+birth)\s*[:#].*$","[REDACTED]",t)
    t = re.sub(r"(?i)\bDOB\s*[:#]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b","[DOB]",t)
    t = re.sub(r"(?i)\b(date\s+of\s+birth)\s*[:#]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b","[DOB]",t)
    t = re.sub(r"(?i)\b(\d{1,3})\s*(?:year[- ]?old|y/o|yo|yrs?|years?)\b","[AGE]",t)
    t = re.sub(r"(?i)\b(?:male|female)\b","[SEX]",t)
    t = re.sub(r"(?i)\b(\d{1,3})\s*/\s*(m|f)\b","[AGE/SEX]",t)
    t = re.sub(r"(?i)\b(\d{1,3})(m|f)\b","[AGE/SEX]",t)
    t = re.sub(r"(?im)^(\s*(indication|reason|history)\s*:\s*)[A-Z][A-Za-z'.-]+(?:\s+[A-Z][A-Za-z'.-]+){0,2},\s*",r"\1",t)
    return t

# ---------- helpers ----------
def _normalize_listish(text: str) -> List[str]:
    t = (text or "").strip()
    # JSON array
    try:
        val = json.loads(t)
        if isinstance(val, list):
            return [re.sub(r"^\s*[\-\*\u2022]\s*", "", str(x or "").strip()) for x in val if str(x or "").strip()]
    except Exception:
        pass
    # Python literal list: ['a', 'b']
    try:
        if re.match(r"^\s*\[.*\]\s*$", t, flags=re.S):
            val = ast.literal_eval(t)
            if isinstance(val, list):
                return [re.sub(r"^\s*[\-\*\u2022]\s*", "", str(x or "").strip()) for x in val if str(x or "").strip()]
    except Exception:
        pass
    # Bullet lines
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    bullets = [re.sub(r"^\s*[\-\*\u2022]\s*", "", ln) for ln in lines if re.match(r"^\s*[\-\*\u2022]", ln)]
    if bullets:
        return bullets
    # Semicolon list
    if ";" in t and not re.search(r"[.!?]\s*$", t):
        parts = [p.strip() for p in t.split(";") if p.strip()]
        if len(parts) > 1:
            return parts
    return []

def _split_sentences(s: str) -> List[str]:
    t = re.sub(r"\s+", " ", s or "").strip()
    return re.split(r"(?<=[.!?])\s+", t) if t else []

def _round_number_token(tok: str) -> str:
    try:
        f = float(tok); return str(int(round(f))) if abs(f) >= 10 else f"{round(f,1):g}"
    except Exception:
        return tok

def _convert_units(s: str) -> str:
    def conv_dim(m: re.Match) -> str:
        nums = re.split(r"\s*[x×]\s*", m.group(1)); unit = m.group(2).lower(); out: List[str] = []
        if unit == "mm":
            for t in nums:
                try:
                    val = float(t); out.append(f"{round(val/10.0,1):g}" if val>=10 else f"{round(val,1):g} mm")
                except Exception: out.append(t)
            return (" x ".join(out) + (" cm" if all(not x.endswith("mm") for x in out) else ""))
        if unit == "cm":
            for t in nums: out.append(_round_number_token(t))
            return " x ".join(out) + " cm"
        return m.group(0)
    s = re.sub(r"((?:\d+(?:\.\d+)?)(?:\s*[x×]\s*(?:\d+(?:\.\d+)?)){1,3})\s*(mm|cm)\b", conv_dim, s)
    def conv_single(m: re.Match) -> str:
        val = float(m.group(1)); unit = m.group(2).lower()
        if unit=="mm" and val>=10: return f"{round(val/10.0,1):g} cm"
        if unit=="cm" and val<0.1:  return f"{round(val*10.0,1):g} mm"
        return f"{_round_number_token(m.group(1))} {unit}"
    return re.sub(r"\b(\d+(?:\.\d+)?)\s*(mm|cm)\b", conv_single, s)

def _numbers_simple(text_only: str) -> str:
    s = text_only or ""
    s = _convert_units(s)
    s = re.sub(r"(?<!\w)(\d+\.\d+|\d+)(?!\w)", lambda m: _round_number_token(m.group(0)), s)
    return re.sub(r"(?<=\d)\s*[x×]\s*(?=\d)", " x ", s)

def _grammar_cleanup(s: str) -> str:
    s = re.sub(r"\bare looks\b", "look", s or "", flags=re.I)
    s = re.sub(r"\bis looks\b", "looks", s, flags=re.I)
    s = re.sub(r"\bare appears?\b", "appear", s, flags=re.I)
    s = re.sub(r"\bis appear\b", "appears", s, flags=re.I)
    s = re.sub(r"\bis\s+noted\b", "", s, flags=re.I)
    s = re.sub(r"\bis\s+seen\b", "", s, flags=re.I)
    s = re.sub(r"\s+\.", ".", s); s = re.sub(r"\s+,", ",", s); s = re.sub(r"\s{2,}", " ", s)
    return s.strip()

def _fix_swelling_phrasing(s: str) -> str:
    t = s or ""
    # "There is swelling in X" -> "Swelling in X"
    t = re.sub(r"(?i)\bthere\s+(?:is|was|are)\s+swelling\s+in\s+([a-z][a-z\s\-]{2,})",
               lambda m: f"Swelling in {m.group(1).strip()}", t)
    # "swelling of X" -> "Swelling in X"
    t = re.sub(r"(?i)\bswelling\s+of\s+([a-z][a-z\s\-]{2,})",
               lambda m: f"Swelling in {m.group(1).strip()}", t)
    # "X swelling" -> "Swelling in X"
    t = re.sub(r"\b([A-Za-z][A-Za-z\s\-]{3,})\s+swelling\b",
               lambda m: f"Swelling in {m.group(1).strip()}", t)
    # Cleanup double inserts
    t = re.sub(r"(?i)\bSwelling in\s+(there\s+(?:is|are)\s+)", "Swelling in ", t)
    return t

_PHRASE_TIDY = [
    (re.compile(r"\bRight\s+fronto\s*parietal\b", re.I), "Right frontoparietal"),
    (re.compile(r"\bFronto\s*parietal\b", re.I), "frontoparietal"),
    (re.compile(r"\boutside the brain tissue\s+enhances with contrast dye\s+(tumou?r)\b", re.I), r"\1 outside the brain tissue that enhances with contrast dye"),
    (re.compile(r"\benhances with contrast dye\s+(tumou?r)\b", re.I), r"\1 that enhances with contrast dye"),
    (re.compile(r"\boutside the brain tissue\s+(tumou?r)\b", re.I), r"\1 outside the brain tissue"),
]
def _tidy_phrases(s: str) -> str:
    out = s or ""
    for rx, repl in _PHRASE_TIDY: out = rx.sub(repl, out)
    return out

def _dedupe_redundant_noun_phrase(s: str) -> str:
    """Within each sentence, replace 'may/might be a(n) X' with 'is indeterminate'
    only when X already appears earlier in that same sentence."""
    nouns = ["mass", "lesion", "tumor", "tumour", "cyst", "nodule", "polyp"]
    out_sents: List[str] = []
    for sent in _split_sentences(s or ""):
        t = sent
        for n in nouns:
            # if noun appears earlier in the sentence
            if re.search(rf"(?i)\b{re.escape(n)}\b", t):
                # replace trailing hedge about same noun
                t = re.sub(
                    rf"(?i)\b(?:may|might)\s+be\s+a?n?\s+{re.escape(n)}\b",
                    "is indeterminate",
                    t,
                )
        out_sents.append(t)
    return " ".join(out_sents)


def _strip_signatures(s: str) -> str:
    s = re.sub(r"(?im)^\s*(dr\.?.*|consultant\s*radiologist.*|radiologist.*|dictated\s+by.*)\s*$","",s or "")
    s = re.sub(r"(?im)^\s*(signed|electronically\s+signed.*)\s*$","",s); return s.strip()

def _unwrap_soft_breaks(s: str) -> str:
    s = (s or "").replace("\r\n","\n").replace("\r","\n")
    s = re.sub(r"-\s*\n(?=\w)","",s); s = re.sub(r"[ \t]+\n","\n",s); s = re.sub(r"\n[ \t]+","\n",s)
    s = re.sub(r"(?<!\n)\n(?!\n)"," ",s)
    return re.sub(r"\n{3,}","\n\n",s)

def _is_caps_banner(ln: str) -> bool:
    if not ln or len(ln) < 8: return False
    letters = re.sub(r"[^A-Za-z]","",ln)
    if not letters: return False
    upper_ratio = sum(c.isupper() for c in letters) / max(1,len(letters))
    tokens = len(ln.split())
    has_modality = bool(re.search(r"\b(MRI|CT|US|XR)\b", ln))
    return (upper_ratio >= 0.85 and tokens >= 8 and not has_modality)

def _preclean_report(raw: str) -> str:
    if not raw: return ""
    s = _unwrap_soft_breaks(raw)
    lines = [ln.strip() for ln in s.split("\n")]
    start_rx = re.compile(r"(?i)\b(history|indication|reason|technique|procedure|findings?|impression|conclusion|report|scan|mri|ct|ultrasound|usg|axial|cect|nect)\b")
    drop_exact = re.compile(r"(?i)^(report|summary|x-?ray|ct\s+head|ct\s+brain)$")
    drop_keyval = re.compile(r"(?i)^\s*(ref(\.|:)?\s*no|ref|date|name|age|sex|gender|mrn|id|file|account|acct|dob|date\s+of\s+birth)\s*[:#].*$")
    start = 0
    for i, ln in enumerate(lines):
        if start_rx.search(ln):
            start = i; break
    kept: List[str] = []
    for ln in lines[start:]:
        if not ln or drop_exact.match(ln) or drop_keyval.match(ln) or _is_caps_banner(ln):
            continue
        kept.append(ln)
    cleaned: List[str] = []
    for ln in kept:
        if not cleaned or cleaned[-1] != ln: cleaned.append(ln)
    return "\n".join(cleaned)

def _extract_history(cleaned: str) -> Tuple[str, str]:
    pattern = re.compile(r"(?im)^\s*(?:clinical\s*(?:hx|history)|history|indication)\s*:\s*([^\n.]+)\.?\s*$")
    outs = [m.group(1).strip() for m in pattern.finditer(cleaned or "")]
    text_wo = pattern.sub("", cleaned or "")
    return ("; ".join(dict.fromkeys(outs)).strip(), text_wo)

def _strip_labels(s: str) -> str:
    s = s or ""
    s = re.sub(r"(?im)^\s*(reason|indication|procedure|technique|findings?|impression|conclusion|summary|ddx)\s*:\s*", "", s)
    return re.sub(r"(?i)\b(findings?|impression|conclusion|summary|ddx)\s*:\s*", "", s).strip()

def _simplify(text: str, gloss: Glossary | None) -> str:
    s = text or ""
    if gloss: s = gloss.replace_terms(s)
    s = re.sub(r"\bcm\b"," centimeters",s,flags=re.I); s = re.sub(r"\bmm\b"," millimeters",s,flags=re.I)
    s = re.sub(r"\bHU\b"," Hounsfield units",s,flags=re.I)
    s = re.sub(r"\bunremarkable\b","looks normal",s,flags=re.I)
    s = re.sub(r"\bintact\b","normal",s,flags=re.I)
    s = re.sub(r"\bsymmetric\b","same on both sides",s,flags=re.I)
    s = re.sub(r"\bbenign\b","not dangerous",s,flags=re.I)
    s = _rewrite_jargon(s); s = _numbers_simple(s); s = _fix_swelling_phrasing(s); s = _grammar_cleanup(s); s = _tidy_phrases(s)
    return s.strip()

# ---------- tooltip wrappers ----------
def _escape_attr(s: str) -> str:
    s = s or ""
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#x27;")

def _annotate_terms_onepass(text_only: str) -> str:
    if not text_only: return ""
    matches: List[Tuple[int,int,str,str]] = []
    for rx, d in _TERM_REGEX:
        for m in rx.finditer(text_only):
            matches.append((m.start(), m.end(), m.group(0), d))
    if not matches: return text_only
    matches.sort(key=lambda t: (t[0], -(t[1]-t[0])))
    kept: List[Tuple[int,int,str,str]] = []; last_end = -1
    for s,e,vis,d in matches:
        if s < last_end: continue
        kept.append((s,e,vis,d)); last_end = e
    out: List[str] = []; pos = 0
    for s,e,vis,d in kept:
        if s > pos: out.append(text_only[pos:s])
        out.append(f'<span class="term-def" data-def="{_escape_attr(d)}">{_escape_attr(vis)}</span>')
        pos = e
    out.append(text_only[pos:]); return "".join(out)

def _annotate_terms_outside_tags(htmlish: str) -> str:
    parts = re.split(r"(<[^>]+>)", htmlish or "")
    for i in range(0,len(parts),2): parts[i] = _annotate_terms_onepass(parts[i])
    return "".join(parts)

# ---------- phrase-aware highlighting ----------
_POS_SENTENCE_RX = re.compile(r"(?i)\b(no|none|without|absent|free of|negative for|not seen|no evidence of|no significant)\b")
_NEG_RXES = [re.compile(p, re.I) for p in NEG_PHRASES] + [re.compile(rf"(?i)\b{re.escape(w)}\b") for w in NEG_WORDS]
_POS_RX = re.compile(r"(?i)\b(normal|benign|unremarkable|clear|symmetric|intact|stable|improved)\b")
_NO_RX = re.compile(r"(?i)(no\s+(?:[a-z/-]+(?:\s+[a-z/-]+){0,3}))")
_WITHOUT_RX = re.compile(r"(?i)(without\s+(?:[a-z/-]+(?:\s+[a-z/-]+){0,3}))")

def _has_neg_term(s: str) -> bool: return any(rx.search(s) for rx in _NEG_RXES)
def _has_pos_cue(s: str) -> bool: return bool(_POS_SENTENCE_RX.search(s))

def _wrap_green(t: str) -> str: return f'<span class="ii-pos" style="color:#22c55e;font-weight:600">{t}</span>'
def _wrap_red(tok: str, defn: str = "") -> str:
    data = f' data-def="{_escape_attr(defn)}"' if defn else ""
    return f'<span class="ii-neg" style="color:#ef4444;font-weight:600"{data}>{tok}</span>'

def _highlight_phrasewise(text: str) -> str:
    s = text or ""; low = s.lower()
    if _has_neg_term(low) and _has_pos_cue(low):
        return f'<span class="ii-text" style="color:#ffffff">{_wrap_green(s)}</span>'
    t = s
    for rx in _NEG_RXES:
        def _neg_repl(m: re.Match) -> str:
            tok = m.group(0); key = tok.lower(); defn = NEG_DEFS.get(key, NEG_DEFS.get(key.strip().lower(), ""))
            return _wrap_red(tok, defn)
        t = rx.sub(_neg_repl, t)
    t = _NO_RX.sub(lambda m: _wrap_green(m.group(0)), t)
    t = _WITHOUT_RX.sub(lambda m: _wrap_green(m.group(0)), t)
    t = _POS_RX.sub(lambda m: _wrap_green(m.group(0)), t)
    return f'<span class="ii-text" style="color:#ffffff">{t}</span>'

# ---------- JSON utils ----------
def _extract_json_loose(s: str) -> Dict[str, str] | None:
    if not s: return None
    try: return json.loads(s)
    except Exception:
        m = re.search(r"\{.*\}", s, flags=re.S)
        if not m: return None
        try: return json.loads(m.group(0))
        except Exception: return None

# ---------- Model resolution ----------
def _supports_chat_completions(m: str) -> bool:
    m = (m or "").lower()
    return any(p in m for p in ["gpt-4", "gpt-4o", "gpt-4o-mini", "3.5", "mini"])

def _is_reasoning_model(m: str) -> bool:
    m = (m or "").lower()
    return any(x in m for x in ["gpt-5", "o3", "o4-mini-high"])

def _resolve_models() -> Tuple[str, str]:
    """Return (env_model, chat_fallback). chat_fallback must support JSON mode."""
    env_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    chat_fallback = os.getenv("OPENAI_CHAT_FALLBACK", "gpt-4o-mini")
    return (env_model, chat_fallback)

# ---------- OpenAI ----------
def _call_openai_once(report_text: str, language: str, temperature: float, effort: str) -> Dict[str, str] | None:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    env_model, chat_fallback = _resolve_models()

    instructions = f"""You summarize medical imaging reports for the public. Write all output in {language}.
Return ONLY a JSON object with keys: reason, technique, findings, conclusion, concern.
Audience is a 13-year-old. Short sentences. Use plain words.
reason and technique: 1–2 short sentences; findings and conclusion: 2–4; concern: 1–2.
Round numbers. Use cm unless under 1 cm, then mm. Findings: bullet list. Conclusion: 1–2 bullets. No names."""

    # 1) Try Chat Completions JSON mode when supported.
    chat_model = env_model if _supports_chat_completions(env_model) else chat_fallback
    tried_chat = False
    if chat_model:
        try:
            from openai import APIStatusError  # present in newer sdks; ignore if missing
        except Exception:
            APIStatusError = Exception  # type: ignore

        try:
            tried_chat = True
            resp = client.chat.completions.create(
                model=chat_model,
                messages=[
                    {"role":"system","content":instructions},
                    {"role":"user","content":report_text},
                ],
                temperature=float(os.getenv("OPENAI_TEMPERATURE","0.2")),
                max_tokens=900,
                response_format={"type":"json_object"},
            )
            data = _extract_json_loose(resp.choices[0].message.content) or {}
            if data:
                out: Dict[str,str] = {}
                for k in ("reason","technique","findings","conclusion","concern"):
                    v = data.get(k,"")
                    out[k] = (v if isinstance(v,str) else str(v or "")).strip()
                return out
        except NotFoundError as e:
            logger.error("Chat model not found: %s", getattr(e, "message", str(e)))
        except BadRequestError as e:
            logger.error("Chat 400 for model=%s: %s", chat_model, getattr(e, "message", str(e)))
        except APIStatusError as e:  # network/http class
            logger.error("Chat APIStatusError: %s", str(e))
        except Exception:
            logger.exception("OpenAI chat call failed")

    # 2) Fallback to Responses for reasoning models or when chat failed.
    model = env_model
    use_temp = not _is_reasoning_model(model)  # temperature often unsupported on reasoning models
    kwargs = dict(
        model=model,
        instructions=instructions,
        input=report_text,
        max_output_tokens=int(os.getenv("OPENAI_MAX_OUTPUT_TOKENS","1500")),
    )
    if use_temp:
        kwargs["temperature"] = temperature
    if effort in {"low","medium","high","minimal"} and _is_reasoning_model(model):
        kwargs["reasoning"] = {"effort": effort}

    try:
        resp = client.responses.create(**kwargs)
        text = getattr(resp, "output_text", None) or str(resp)
        data = _extract_json_loose(text) or {}
    except BadRequestError as e:
        msg = getattr(e, "message", str(e))
        logger.error("Responses 400 for model=%s: %s", model, msg)
        # Retry once without temperature if that was the complaint.
        if "Unsupported parameter: 'temperature'" in msg or "temperature" in msg.lower():
            kwargs.pop("temperature", None)
            try:
                resp = client.responses.create(**kwargs)
                text = getattr(resp, "output_text", None) or str(resp)
                data = _extract_json_loose(text) or {}
            except Exception:
                logger.exception("Responses retry without temperature failed")
                data = {}
        else:
            data = {}
    except NotFoundError as e:
        logger.error("Responses model not found: %s", getattr(e, "message", str(e)))
        data = {}
    except Exception:
        logger.exception("OpenAI responses call failed")
        data = {}

    out: Dict[str,str] = {}
    for k in ("reason","technique","findings","conclusion","concern"):
        v = data.get(k,"")
        out[k] = (v if isinstance(v,str) else str(v or "")).strip()
    return out

def _merge_runs(runs: List[Dict[str, str]]) -> Dict[str, str]:
    def norm(x: str) -> str:
        return re.sub(r"\s+"," ", _strip_labels((x or "").strip()).lower())
    out: Dict[str, str] = {}
    for key in ("reason","technique","findings","conclusion","concern"):
        vals = [r.get(key,"") for r in runs if r.get(key)]
        if not vals: out[key] = ""; continue
        counts: Dict[str, Tuple[int,str]] = {}
        for v in vals:
            n = norm(v)
            if n in counts:
                prev_n, prev_v = counts[n]
                counts[n] = (prev_n + 1, prev_v if len(prev_v) >= len(v) else v)
            else:
                counts[n] = (1, v)
        pick = sorted(counts.items(), key=lambda kv: (kv[1][0], len(kv[1][1])), reverse=True)[0][1][1]
        out[key] = pick
    return out

def _summarize_with_openai(report_text: str, language: str) -> Dict[str, str] | None:
    if not (os.getenv("INSIDEIMAGING_ALLOW_LLM","0")=="1" and os.getenv("OPENAI_API_KEY")):
        logger.info("[LLM] disabled or missing API key"); return None
    try:
        n = max(1, int(os.getenv("OPENAI_SELF_CONSISTENCY_N","1")))
        effort = (os.getenv("OPENAI_REASONING_EFFORT","") or "").lower()
        base_temp = float(os.getenv("OPENAI_TEMPERATURE","0.2"))
        runs: List[Dict[str,str]] = []
        for i in range(n):
            runs.append(_call_openai_once(report_text, language, min(1.0, base_temp+0.05*i), effort) or {})
        return (_merge_runs(runs) if len(runs)>1 else runs[0]) or None
    except Exception:
        logger.exception("[LLM] summarization failed"); return None

# ---------- extraction ----------
HEAD_WORD = re.compile(r"\b(head|skull|brain)\b", re.I)

def _region_from_text(low: str) -> str | None:
    if any(w in low for w in ["pancreas","pancreatic","liver","hepatic","biliary","gallbladder","kidney","renal","spleen","stomach","bowel","colon"]):
        return "abdomen"
    if any(w in low for w in ["pelvis","uterus","ovary","prostate","bladder","adnexa"]):
        return "pelvis"
    if any(w in low for w in ["chest","thorax","lung","mediastinum","cardiac","heart"]):
        return "chest"
    if any(w in low for w in ["cervical spine","c-spine"]):
        return "cervical spine"
    if any(w in low for w in ["thoracic spine"]):
        return "thoracic spine"
    if any(w in low for w in ["lumbar spine","l-spine","lspine"]):
        return "lumbar spine"
    if ("neck" in low) or ("cervical" in low and "spine" not in low):
        return "neck"
    if HEAD_WORD.search(low) and not re.search(r"\b(head\s+of\s+the\s+pancreas|pancreatic\s+head)\b", low):
        return "head"
    return None

def _extract_technique_details(text: str) -> str:
    low = (text or "").lower()
    modality = "CT" if re.search(r"\bct\b", low) else ("MRI" if "mri" in low else ("Ultrasound" if ("ultrasound" in low or "sonograph" in low) else ("X-ray" if re.search(r"x-?ray|radiograph", low) else None)))
    region = _region_from_text(low)
    planes = [p for p in ["axial","coronal","sagittal"] if p in low]
    has_c = bool(re.search(r"\b(cect|contrast[-\s]?enhanced|with\s+contrast)\b", low))
    has_nc = bool(re.search(r"\b(nect|non[-\s]?contrast|without\s+contrast)\b", low))
    contrast = "with and without contrast" if (has_c and has_nc) else ("with contrast" if has_c else ("without contrast" if has_nc else ""))
    m = re.search(r"from\s+(.+?)\s+to\s+(.+?)[\.;]", text, flags=re.I)
    coverage = f"coverage from {m.group(1).strip()} to {m.group(2).strip()}" if m else ""
    win = "brain window" if "brain window" in low else ""
    parts = []
    if modality: parts.append(f"{'CT scan' if modality=='CT' else modality} of the {region or 'area'}")
    if planes: parts.append(", ".join(planes))
    if contrast: parts.append(contrast)
    if coverage: parts.append(coverage)
    if win: parts.append(win)
    out = ", ".join(parts).strip(", ")
    if out and not out.endswith("."): out += "."
    return out

def _infer_modality_and_region(text: str) -> str:
    low = (text or "").lower()
    modality = "MRI" if "mri" in low else ("CT" if re.search(r"\bct\b", low) else ("Ultrasound" if ("ultrasound" in low or "sonograph" in low) else ("X-ray" if re.search(r"x-?ray|radiograph", low) else None)))
    with_contrast = bool(re.search(r"\b(contrast|cect)\b", low))
    region = _region_from_text(low)
    if not modality: return ""
    if region:
        return f"{'CT scan' if modality=='CT' else modality} of the {region}" + (" with contrast." if modality=='CT' and with_contrast else ".")
    return f"{'CT scan' if modality=='CT' else modality}" + (" with contrast." if modality=='CT' and with_contrast else ".")

def _infer_reason(text: str, seed: str) -> str:
    src = seed or ""
    if not src or src.strip().lower() == "not provided.":
        m = re.search(r"(?im)^\s*(indication|reason|history)\s*:\s*(.+)$", text or "")
        if m:
            src = m.group(2).strip()

    low_all = (text or "").lower() + " " + (src or "").lower()

    region = "head" if any(w in low_all for w in ["head","skull","brain"]) else \
             "neck" if "neck" in low_all else \
             "abdomen" if any(w in low_all for w in ["abdomen","abdominal","belly","pancreas","pancreatic","biliary","liver","hepatic","gallbladder"]) else \
             "area"

    has_mass = bool(re.search(r"\b(mass|lesion|tumou?r|nodule|cyst)\b", low_all))
    has_nodes = bool(re.search(r"\b(adenopathy|lymph\s*node|lymphaden)\b", low_all))

    p1 = "The scan was done to check for a mass." if has_mass else f"The scan was done to look for a problem in the {region}."
    if has_nodes:
        p1 = p1.rstrip(".") + " and swollen lymph nodes."
    p2 = "The goal was to find a simple cause for the symptoms."
    return f"{p1} {p2}"


# ---------- dedupe and pruning ----------
def _drop_heading_labels_line(s: str) -> str:
    return re.sub(r"(?i)^\s*(findings?|impression|conclusion|summary)\s*:\s*", "", s or "").strip()

def _normalize_sentence(s: str) -> str:
    t = _drop_heading_labels_line(s or "")
    t = re.sub(r"[^a-z0-9\s]", "", t.lower()); t = re.sub(r"\s+"," ",t).strip()
    return t

def _dedupe_sections(findings_text: str, conclusion_text: str) -> Tuple[str, str]:
    f_sents = [_drop_heading_labels_line(x) for x in _split_sentences(findings_text or "")]
    c_sents = [_drop_heading_labels_line(x) for x in _split_sentences(conclusion_text or "")]
    c_norm = {_normalize_sentence(x) for x in c_sents if x}
    f_keep = [s for s in f_sents if _normalize_sentence(s) not in c_norm]
    def uniq(seq: List[str]) -> List[str]:
        seen = set(); out = []
        for s in seq:
            n = _normalize_sentence(s)
            if n and n not in seen: seen.add(n); out.append(s)
        return out
    f_keep = uniq(f_keep); c_keep = uniq(c_sents)
    return (" ".join(f_keep).strip(), " ".join(c_keep).strip())

def _prune_findings_for_public(text: str) -> str:
    kept: List[str] = []
    for sent in _split_sentences(text or ""):
        s = _grammar_cleanup(sent.strip())
        if not s or NOISE_RX.search(s): continue
        low = s.lower()
        has_number = bool(re.search(r"\b\d+(\.\d+)?\s*(mm|cm)\b", low))
        is_key = any(re.search(p, low) for p in [*NEG_PHRASES, r"\bmass\b", r"\bfracture\b", r"\bhernia\b", r"\bherniation\b", r"\bstenosis\b"])
        is_pos_blanket = bool(re.match(r"(?i)^(the\s+rest|other\s+areas)\b", s))
        if re.match(r"(?i)^\s*(impression|conclusion|summary)\s*:", s): continue
        if is_key or has_number or is_pos_blanket: kept.append(s)
    return " ".join(kept[:4])

def _to_colored_bullets_html(raw: str, max_items: int, include_normal: bool) -> str:
    items: List[str] = []
    sources = _normalize_listish(raw) or _split_sentences(raw or "")
    for s in sources:
        s = _drop_heading_labels_line(s)
        t = _tidy_phrases(_grammar_cleanup(_numbers_simple(_simplify(s, None))))
        t = _dedupe_redundant_noun_phrase(t)
        if not t:
            continue
        items.append(_highlight_phrasewise(t))
        if len(items) >= max_items - (1 if include_normal else 0):
            break
    if include_normal:
        items.append(_highlight_phrasewise("Most other areas look normal."))
    if not items:
        items = [_highlight_phrasewise("No major problems were seen.")]
    html = "<ul class='ii-list' style='color:#ffffff'>" + "".join(f"<li>{it}</li>" for it in items[:max_items]) + "</ul>"
    return _annotate_terms_outside_tags(html)

# ---------- main API ----------
def build_structured(
    text: str,
    lay_gloss: Glossary | None = None,
    language: str = "English",
    render_style: str = "bullets",
) -> Dict[str, str]:
    try:
        lat_ms = max(0, int(os.getenv("OPENAI_MIN_LATENCY_MS","0")))
        if lat_ms: time.sleep(min(10.0, lat_ms/1000.0))
    except Exception:
        pass

    meta = parse_metadata(text or "")
    cleaned = _preclean_report(text or "")

    hx, cleaned = _extract_history(cleaned)
    secs = sections_from_text(cleaned)

    reason_seed = secs.get("reason") or "Not provided."
    if hx: reason_seed = (reason_seed.rstrip(".") + f". History: {hx}.").strip()
    findings_src = _strip_signatures(secs.get("findings") or (cleaned or "Not described."))
    impression_src = _strip_signatures(secs.get("impression") or "")

    m = re.search(r"(?mi)^\s*comparison\s*:\s*(.+)$", cleaned); comparison = (m.group(1).strip() if m else "")
    m = re.search(r"(?mi)^\s*oral\s+contrast\s*:\s*(.+)$", cleaned); oral_contrast = (m.group(1).strip() if m else "")

    fallback_findings = _simplify(_prune_findings_for_public(findings_src), lay_gloss)
    base_conc = impression_src or ""
    if not base_conc:
        picks: List[str] = []
        for kw in ["mass","obstruction","compression","dilation","fracture","bleed","appendicitis","adenopathy","necrotic","atrophy","stenosis","herniation"]:
            m2 = re.search(rf"(?is)([^.]*\b{kw}\b[^.]*)\.", cleaned)
            if m2: picks.append(m2.group(0).strip())
        base_conc = " ".join(dict.fromkeys(picks))
    fallback_conclusion = _simplify(_strip_labels(base_conc) or "See important findings.", lay_gloss)

    concern = ""
    for kw in ["obstruction","compression","invasion","perforation","ischemia"]:
        if re.search(rf"(?i)\b{kw}\b", cleaned):
            concern = f"The findings include {kw}. Discuss next steps with your clinician."
            break
    # no else/fallback here

    # LLM attempt, gated + PHI-redacted
    llm = _summarize_with_openai(_redact_phi(cleaned), language)
    llm_reason = _strip_labels((llm or {}).get("reason","")) if llm else ""
    llm_tech = _strip_labels((llm or {}).get("technique","")) if llm else ""

    raw_findings = (_simplify(_strip_labels((llm or {}).get("findings","")), lay_gloss) if llm else "") or fallback_findings
    raw_conclusion = (_simplify(_strip_labels((llm or {}).get("conclusion","")), lay_gloss) if llm else "") or fallback_conclusion

    # remove overlap
    raw_findings, raw_conclusion = _dedupe_sections(raw_findings, raw_conclusion)

    concern_txt = (_simplify((llm or {}).get("concern",""), lay_gloss) if llm else "") or concern

    # technique prefer deterministic
    technique_extracted = _extract_technique_details(cleaned) or _infer_modality_and_region(cleaned)
    technique_txt = technique_extracted or _simplify(llm_tech, lay_gloss) or "Technique not described."

    # reason
    reason_txt = _infer_reason(cleaned, llm_reason or reason_seed)

    # render
    findings_html = _to_colored_bullets_html(raw_findings, max_items=4, include_normal=True)
    conclusion_html = _to_colored_bullets_html(raw_conclusion, max_items=2, include_normal=False)
    reason_html = _annotate_terms_outside_tags(f'<span class="ii-text" style="color:#ffffff">{_simplify(reason_txt, lay_gloss)}</span>')
    technique_html = _annotate_terms_outside_tags(f'<span class="ii-text" style="color:#ffffff">{_simplify(technique_txt, lay_gloss)}</span>')
    concern_html = _annotate_terms_outside_tags(f'<span class="ii-text" style="color:#ffffff">{_simplify(concern_txt, lay_gloss)}</span>') if concern_txt else ""

    # stats
    words = len(re.findall(r"\w+", cleaned or ""))
    sentences = len(re.findall(r"[.!?]+", cleaned or ""))
    pos_hi = len(re.findall(r'class="ii-pos"', findings_html + conclusion_html))
    neg_hi = len(re.findall(r'class="ii-neg"', findings_html + conclusion_html))

    return {
        "name": meta.get("name",""), "age": meta.get("age",""), "sex": meta.get("sex",""),
        "hospital": meta.get("hospital",""), "date": meta.get("date",""), "study": meta.get("study",""),
        "reason": reason_html.strip(), "technique": technique_html.strip(),
        "comparison": comparison or "None", "oral_contrast": oral_contrast or "Not stated",
        "findings": findings_html.strip(), "conclusion": conclusion_html.strip(), "concern": concern_html.strip(),
        "word_count": words, "sentence_count": sentences, "highlights_positive": pos_hi, "highlights_negative": neg_hi,
    }

__all__ = ["Glossary", "build_structured"]
