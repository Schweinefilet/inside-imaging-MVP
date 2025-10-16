# src/translate.py
from __future__ import annotations

import csv, re, os, json, logging
from dataclasses import dataclass
from typing import Dict, List, Tuple

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
        blocks = re.split(r"\n\s*\n", text or "")
        whole = " ".join(b.strip() for b in blocks if b.strip())
        return {"reason": "", "technique": "", "findings": whole, "impression": ""}

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
POS_WORDS = [
    "normal", "benign", "unremarkable", "clear", "symmetric", "intact", "stable", "improved", "no ", "without "
]
NEG_WORDS = [
    "mass", "tumor", "cancer", "lesion", "adenopathy", "enlarged", "necrotic", "metastasis",
    "obstruction", "compression", "invasion", "perforation", "ischemia", "fracture", "bleed",
    "hydroureteronephrosis", "hydroureter", "hydronephrosis", "herniation", "shift", "edema",
    "swelling", "atrophy",
]
NEG_PHRASES = [
    r"mass\s+effect",
    r"subfalcine\s+herniation",
    r"midline\s+shift",
    r"perilesional\s+edema",
]

NEG_DEFS: Dict[str, str] = {
    "mass": "an abnormal lump that can press on tissue",
    "tumor": "a growth that forms a lump",
    "cancer": "a harmful growth that can spread",
    "lesion": "an abnormal spot or area",
    "adenopathy": "swollen lymph nodes",
    "enlarged": "bigger than normal",
    "necrotic": "dead tissue",
    "metastasis": "spread to other areas",
    "obstruction": "a blockage",
    "compression": "being pressed by something",
    "invasion": "growing into nearby tissues",
    "perforation": "a hole or tear",
    "ischemia": "low blood flow",
    "fracture": "a broken bone",
    "bleed": "bleeding",
    "herniation": "tissue pushed into an abnormal space",
    "edema": "swelling",
    "atrophy": "shrinking of tissue",
    # phrases
    "mass effect": "pressure on brain structures",
    "subfalcine herniation": "brain shifted under the central fold",
    "midline shift": "brain pushed off center",
    "perilesional edema": "swelling around the lesion",
}

# Plain-language rewrites that keep clinical term readable
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
]

def _rewrite_jargon(s: str) -> str:
    out = s or ""
    for rx, repl in _JARGON_MAP:
        out = rx.sub(repl, out)
    return out

# concise medical tooltips
_TERM_DEFS = [
    {"pat": r"\bmeningioma\b", "def": "tumor from the brain’s lining"},
    {"pat": r"\bextra[-\s]?axial\b", "def": "outside brain tissue but inside skull"},
    {"pat": r"\bsubfalcine\s+herniation\b", "def": "brain pushed under central fold"},
    {"pat": r"\bmass\s+effect\b", "def": "pressure or shift caused by a mass"},
    {"pat": r"\bperilesional\s+edema\b", "def": "swelling around a lesion"},
    {"pat": r"\bgreater\s+sphenoid\s+wing\b", "def": "part of skull bone near the temple"},
    {"pat": r"\bventricle[s]?\b", "def": "fluid spaces inside the brain"},
]
_TERM_REGEX: List[Tuple[re.Pattern, str]] = [(re.compile(d["pat"], re.I), d["def"]) for d in _TERM_DEFS]

# ---------- noise ----------
NOISE_RX = re.compile("|".join(
    f"(?:{p})" for p in [
        r"\baxial\b", r"\bNECT\b", r"\bCECT\b", r"\bbrain window\b",
        r"\bimages?\s+are\s+viewed", r"\bappear\s+normal\b", r"\bare\s+normal\b",
        r"\bno\s+abnormalit(y|ies)\b", r"\bnormally\s+developed\b",
        r"\bparanasal\s+sinuses.*(clear|pneumatiz)", r"\bvisuali[sz]ed\s+lower\s+thorax\s+is\s+normal",
    ]), re.I)

# ---------- basic text helpers ----------
def _split_sentences(s: str) -> List[str]:
    t = re.sub(r"\s+", " ", s or "").strip()
    return re.split(r"(?<=[.!?])\s+", t) if t else []

def _round_number_token(tok: str) -> str:
    try:
        f = float(tok)
        return str(int(round(f))) if abs(f) >= 10 else f"{round(f, 1):g}"
    except Exception:
        return tok

def _convert_units(s: str) -> str:
    # Convert "53.7 x 55.8 x 67.3mm" -> "5.4 x 5.6 x 6.7 cm"
    def conv_dim(m: re.Match) -> str:
        nums = re.split(r"\s*[x×]\s*", m.group(1))
        unit = m.group(2).lower()
        out: List[str] = []
        if unit == "mm":
            for t in nums:
                try:
                    val = float(t)
                    if val >= 10:
                        out.append(f"{round(val/10.0, 1):g}")
                    else:
                        out.append(f"{round(val, 1):g} mm")
                except Exception:
                    out.append(t)
            if all(not x.endswith("mm") for x in out):
                return " x ".join(out) + " cm"
            return " x ".join(out)
        if unit == "cm":
            for t in nums:
                out.append(_round_number_token(t))
            return " x ".join(out) + " cm"
        return m.group(0)
    s = re.sub(r"((?:\d+(?:\.\d+)?)(?:\s*[x×]\s*(?:\d+(?:\.\d+)?)){1,3})\s*(mm|cm)\b", conv_dim, s)
    # Single values with unit
    def conv_single(m: re.Match) -> str:
        val = float(m.group(1))
        unit = m.group(2).lower()
        if unit == "mm" and val >= 10:
            return f"{round(val/10.0,1):g} cm"
        if unit == "cm" and val < 0.1:
            return f"{round(val*10.0,1):g} mm"
        return f"{_round_number_token(m.group(1))} {unit}"
    s = re.sub(r"\b(\d+(?:\.\d+)?)\s*(mm|cm)\b", conv_single, s)
    return s

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
    s = re.sub(r"\s+\.", ".", s)
    s = re.sub(r"\s+,", ",", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()

def _fix_swelling_phrasing(s: str) -> str:
    # "brain tissue around the lesion swelling" -> "Swelling in brain tissue around the lesion"
    def _swap(m: re.Match) -> str:
        zone = m.group(1).strip()
        return f"Swelling in {zone}"
    s = re.sub(r"\b([A-Za-z][A-Za-z\s\-]{3,})\s+swelling\b", _swap, s)
    return s

_PHRASE_TIDY: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\bRight\s+fronto\s*parietal\b", re.I), "Right frontoparietal"),
    (re.compile(r"\bFronto\s*parietal\b", re.I), "frontoparietal"),
    (re.compile(r"\boutside the brain tissue\s+enhances with contrast dye\s+(tumou?r)\b", re.I),
     r"\1 outside the brain tissue that enhances with contrast dye"),
    (re.compile(r"\benhances with contrast dye\s+(tumou?r)\b", re.I),
     r"\1 that enhances with contrast dye"),
    (re.compile(r"\boutside the brain tissue\s+(tumou?r)\b", re.I),
     r"\1 outside the brain tissue"),
]

def _tidy_phrases(s: str) -> str:
    out = s or ""
    for rx, repl in _PHRASE_TIDY:
        out = rx.sub(repl, out)
    return out

def _strip_signatures(s: str) -> str:
    s = re.sub(r"(?im)^\s*(dr\.?.*|consultant\s*radiologist.*|radiologist.*|dictated\s+by.*)\s*$", "", s or "")
    s = re.sub(r"(?im)^\s*(signed|electronically\s+signed.*)\s*$", "", s)
    return s.strip()

def _unwrap_soft_breaks(s: str) -> str:
    s = (s or "").replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"-\s*\n(?=\w)", "", s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"(?<!\n)\n(?!\n)", " ", s)
    return re.sub(r"\n{3,}", "\n\n", s)

def _preclean_report(raw: str) -> str:
    if not raw:
        return ""
    s = _unwrap_soft_breaks(raw)
    lines = [ln.strip() for ln in s.split("\n")]
    start_rx = re.compile(r"(?i)\b(history|indication|reason|technique|procedure|findings?|impression|conclusion|report|scan|mri|ct|ultrasound|usg|axial|cect|nect)\b")
    drop_exact = re.compile(r"(?i)^(report|summary|x-?ray|ct\s+head|ct\s+brain)$")
    drop_keyval = re.compile(r"(?i)^\s*(ref(\.|:)?\s*no|ref|date|name|age|sex|mrn|id|file|account|acct)\s*[:#].*$")
    def _is_caps_banner(ln: str) -> bool:
        return len(ln) > 2 and len(ln.split()) <= 8 and bool(re.match(r"^[A-Z0-9 &/.-]+$", ln)) and not re.search(r"\b(MRI|CT|US|XR)\b", ln)
    start = 0
    for i, ln in enumerate(lines):
        if start_rx.search(ln):
            start = i
            break
    kept: List[str] = []
    for ln in lines[start:]:
        if not ln or drop_exact.match(ln) or drop_keyval.match(ln) or _is_caps_banner(ln):
            continue
        kept.append(ln)
    cleaned: List[str] = []
    for ln in kept:
        if not cleaned or cleaned[-1] != ln:
            cleaned.append(ln)
    return "\n".join(cleaned)

def _extract_history(cleaned: str) -> Tuple[str, str]:
    rx = re.compile(r"(?im)\b(clinical\s*(hx|history))\s*:\s*([^.]+)\.?")
    out = [m.group(3).strip() for m in rx.finditer(cleaned or "")]
    text_wo = rx.sub("", cleaned or "")
    return ("; ".join(dict.fromkeys(out)).strip(), text_wo)

def _strip_labels(s: str) -> str:
    s = s or ""
    s = re.sub(r"(?im)^\s*(reason|indication|procedure|technique|findings?|impression|conclusion|ddx)\s*:\s*", "", s)
    return re.sub(r"(?i)\b(findings?|impression|conclusion|ddx)\s*:\s*", "", s).strip()

def _simplify(text: str, gloss: Glossary | None) -> str:
    s = text or ""
    if gloss:
        s = gloss.replace_terms(s)
    s = re.sub(r"\bcm\b", " centimeters", s, flags=re.I)
    s = re.sub(r"\bmm\b", " millimeters", s, flags=re.I)
    s = re.sub(r"\bHU\b", " Hounsfield units", s, flags=re.I)
    s = re.sub(r"\bunremarkable\b", "looks normal", s, flags=re.I)
    s = re.sub(r"\bintact\b", "normal", s, flags=re.I)
    s = re.sub(r"\bsymmetric\b", "same on both sides", s, flags=re.I)
    s = re.sub(r"\bbenign\b", "not dangerous", s, flags=re.I)
    s = _rewrite_jargon(s)
    s = _numbers_simple(s)
    s = _fix_swelling_phrasing(s)
    s = _grammar_cleanup(s)
    s = _tidy_phrases(s)
    return s.strip()

# ---------- term tooltips ----------
def _escape_attr(s: str) -> str:
    s = s or ""
    return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;").replace('"',"&quot;").replace("'","&#x27;")

def _annotate_terms_onepass(text_only: str) -> str:
    if not text_only:
        return ""
    matches: List[Tuple[int, int, str, str]] = []
    for rx, d in _TERM_REGEX:
        for m in rx.finditer(text_only):
            matches.append((m.start(), m.end(), m.group(0), d))
    if not matches:
        return text_only
    matches.sort(key=lambda t: (t[0], -(t[1] - t[0])))
    kept: List[Tuple[int, int, str, str]] = []
    last_end = -1
    for s, e, vis, d in matches:
        if s < last_end:
            continue
        kept.append((s, e, vis, d))
        last_end = e
    out: List[str] = []
    pos = 0
    for s, e, vis, d in kept:
        if s > pos:
            out.append(text_only[pos:s])
        out.append(f'<span class="term-def" data-def="{_escape_attr(d)}">{_escape_attr(vis)}</span>')
        pos = e
    out.append(text_only[pos:])
    return "".join(out)

def _annotate_terms_outside_tags(htmlish: str) -> str:
    parts = re.split(r"(<[^>]+>)", htmlish or "")
    for i in range(0, len(parts), 2):
        parts[i] = _annotate_terms_onepass(parts[i])
    return "".join(parts)

# ---------- red/green highlight (no brackets) ----------
_POS_RX = re.compile(r"(?i)\b(normal|benign|unremarkable|clear|symmetric|intact|stable|improved)\b")
_NO_RX = re.compile(r"(?i)(no\s+(?:[a-z/-]+(?:\s+[a-z/-]+){0,2}))")
_WITHOUT_RX = re.compile(r"(?i)(without\s+(?:[a-z/-]+(?:\s+[a-z/-]+){0,2}))")
_NEG_RXES = [re.compile(p, re.I) for p in NEG_PHRASES] + [re.compile(rf"(?i)\b{re.escape(w)}\b") for w in NEG_WORDS]

def _highlight_html(text: str) -> str:
    s = text or ""
    # negatives → red with tooltip
    for rx in _NEG_RXES:
        def _neg_repl(m: re.Match) -> str:
            tok = m.group(0)
            key = tok.lower()
            defn = NEG_DEFS.get(key, "")
            data = f' data-def="{_escape_attr(defn)}"' if defn else ""
            return f'<span class="ii-neg" style="color:#ef4444;font-weight:600"{data}>{tok}</span>'
        s = rx.sub(_neg_repl, s)
    # positives → green
    def _pos_wrap(t: str) -> str:
        return f'<span class="ii-pos" style="color:#22c55e;font-weight:600">{t}</span>'
    s = _NO_RX.sub(lambda m: _pos_wrap(m.group(0)), s)
    s = _WITHOUT_RX.sub(lambda m: _pos_wrap(m.group(0)), s)
    s = _POS_RX.sub(lambda m: _pos_wrap(m.group(0)), s)
    # default text → white
    return f'<span class="ii-text" style="color:#ffffff">{s}</span>'

# ---------- JSON + OpenAI ----------
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
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        model = os.getenv("OPENAI_MODEL", "gpt-5")

        def _supports_chat_completions(m: str) -> bool:
            m = (m or "").lower()
            return any(p in m for p in ["gpt-3.5", "gpt-4-0613", "gpt-4-1106", "gpt-4-turbo"])

        instructions = f"""
You summarize medical imaging reports for the public. Write all output in {language}.
Return ONLY a JSON object with keys: reason, technique, findings, conclusion, concern.
Audience is a 13-year-old. Short sentences. Use plain words.
reason and technique: 1–2 short sentences; findings and conclusion: 2–4; concern: 1–2.
Round numbers. Use cm unless under 1 cm, then mm.
Findings: bullet list, collapse normals to one bullet. Conclusion: 1–2 bullets. No names.
""".strip()

        json_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {k: {"type": "string"} for k in ["reason","technique","findings","conclusion","concern"]},
            "required": ["reason", "technique", "findings", "conclusion", "concern"],
        }

        kwargs = dict(model=model, instructions=instructions, input=report_text, max_output_tokens=1500)
        try:
            resp = client.responses.create(
                **kwargs,
                response_format={"type": "json_schema", "json_schema": {"name": "public_summary", "schema": json_schema, "strict": True}},
            )
        except TypeError as e:
            if "response_format" in str(e):
                resp = client.responses.create(**kwargs)
            else:
                raise
        except Exception as e:
            msg = str(e).lower()
            if "response_format" in msg or ("unsupported parameter" in msg and "response_format" in msg):
                resp = client.responses.create(**kwargs)
            else:
                raise

        text = getattr(resp, "output_text", None)
        if not text:
            try:
                text = resp.output[0].content[0].text.value  # type: ignore[attr-defined]
            except Exception:
                text = str(resp)
        data = _extract_json_loose(text) or {}

        if not data and _supports_chat_completions(model):
            resp2 = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": instructions}, {"role": "user", "content": report_text}],
                max_tokens=900,
                response_format={"type": "json_object"},
            )
            data = _extract_json_loose(resp2.choices[0].message.content) or {}

        out: Dict[str, str] = {}
        for k in ("reason", "technique", "findings", "conclusion", "concern"):
            v = data.get(k, "")
            out[k] = (v if isinstance(v, str) else str(v or "")).strip()
        return out
    except Exception:
        logger.exception("[LLM] summarization failed")
        return None

# ---------- scan method extraction ----------
def _extract_technique_details(text: str) -> str:
    low = (text or "").lower()
    # modality
    modality = "CT" if (re.search(r"\bct\b", low)) else \
               "MRI" if "mri" in low else "Ultrasound" if ("ultrasound" in low or "sonograph" in low) else \
               "X-ray" if re.search(r"x-?ray|radiograph", low) else None
    # region
    region = "head" if any(w in low for w in ["head","skull","brain"]) else \
             "cervical spine" if any(w in low for w in ["cervical spine","c-spine"]) else \
             "lumbar spine" if any(w in low for w in ["lumbar spine","l-spine","lspine"]) else \
             "thoracic spine" if "thoracic spine" in low else \
             "neck" if "neck" in low else \
             "chest" if any(w in low for w in ["chest","thorax","lung"]) else \
             "abdomen" if any(w in low for w in ["abdomen","abdominal","belly"]) else \
             "pelvis" if "pelvis" in low else None
    # planes
    planes = [p for p in ["axial","coronal","sagittal"] if p in low]
    planes_str = (", ".join(planes)) if planes else ""
    # contrast (handle NECT/CECT tokens too)
    has_c = bool(re.search(r"\b(cect|contrast[-\s]?enhanced|with\s+contrast)\b", low))
    has_nc = bool(re.search(r"\b(nect|non[-\s]?contrast|without\s+contrast)\b", low))
    contrast = "with and without contrast" if (has_c and has_nc) else ("with contrast" if has_c else ("without contrast" if has_nc else ""))
    # coverage
    m = re.search(r"from\s+(.+?)\s+to\s+(.+?)[\.;]", text, flags=re.I)
    coverage = f"coverage from {m.group(1).strip()} to {m.group(2).strip()}" if m else ""
    # windows
    win = "brain window" if "brain window" in low else ""
    parts = []
    if modality:
        parts.append(f"{'CT scan' if modality=='CT' else modality} of the {region or 'area'}")
    if planes_str:
        parts.append(planes_str)
    if contrast:
        parts.append(contrast)
    if coverage:
        parts.append(coverage)
    if win:
        parts.append(win)
    if not parts and modality:
        parts = [f"{'CT scan' if modality=='CT' else modality}"]
    out = ", ".join(parts).strip(", ")
    if out and not out.endswith("."):
        out += "."
    return out

def _infer_modality_and_region(text: str) -> str:
    low = (text or "").lower()
    modality = "MRI" if "mri" in low else "CT" if re.search(r"\bct\b", low) else "Ultrasound" if ("ultrasound" in low or "sonograph" in low) else "X-ray" if re.search(r"x-?ray|radiograph", low) else None
    with_contrast = bool(re.search(r"\b(contrast|cect)\b", low))
    region = "cervical spine" if any(w in low for w in ["cervical spine","c-spine"]) else \
             "lumbar spine" if any(w in low for w in ["lumbar spine","l-spine","lspine"]) else \
             "thoracic spine" if "thoracic spine" in low else \
             "neck" if ("neck" in low or "cervical" in low) else \
             "chest" if any(w in low for w in ["chest","thorax","lung"]) else \
             "abdomen" if any(w in low for w in ["abdomen","abdominal","belly"]) else \
             "pelvis" if "pelvis" in low else \
             "head" if any(w in low for w in ["head","skull","brain"]) else None
    if not modality:
        return ""
    if region:
        return f"{'CT scan' if modality=='CT' else modality} of the {region}" + (" with contrast." if modality=='CT' and with_contrast else ".")
    return f"{'CT scan' if modality=='CT' else modality}" + (" with contrast." if modality=='CT' and with_contrast else ".")

def _infer_reason(text: str, seed: str) -> str:
    src = seed or ""
    if not src or src.strip().lower() == "not provided.":
        m = re.search(r"(?im)^\s*(indication|reason|history)\s*:\s*(.+)$", text or "")
        if m:
            src = m.group(2).strip()
    low = (text or "").lower()
    region = "head" if any(w in low for w in ["head","skull","brain"]) else \
             "neck" if "neck" in low else "area"
    s = _simplify(src, None)
    s = re.sub(r"\b\?\s*", "possible ", s)
    want_lymph = bool(re.search(r"\blymphoma\b", s, flags=re.I))
    want_mass = bool(re.search(r"\bmass\b|\badenopathy\b", s, flags=re.I))
    if want_mass:
        p1 = "The scan was done to check for a mass and swollen nodes."
    else:
        p1 = f"The scan was done to look for a problem in the {region}."
    p2 = "Doctors wanted to see if there were signs of lymphoma." if want_lymph else "The goal was to find a simple cause for the symptoms."
    return f"{p1} {p2}"

# ---------- rendering ----------
def _prune_findings_for_public(text: str) -> str:
    kept: List[str] = []
    for sent in _split_sentences(text or ""):
        s = _grammar_cleanup(sent.strip())
        if not s or NOISE_RX.search(s):
            continue
        low = s.lower()
        has_number = bool(re.search(r"\b\d+(\.\d+)?\s*(mm|cm)\b", low))
        is_key = any(re.search(p, low) for p in [*NEG_PHRASES, r"\bmass\b", r"\bfracture\b", r"\bhernia\b", r"\bherniation\b"])
        is_pos_blanket = bool(re.match(r"(?i)^(the\s+rest|other\s+areas)\b", s))
        if is_key or has_number or is_pos_blanket:
            kept.append(s)
    return " ".join(kept[:4])

def _to_colored_bullets_html(raw: str, max_items: int, include_normal: bool) -> str:
    items: List[str] = []
    for s in _split_sentences(raw or ""):
        t = _tidy_phrases(_grammar_cleanup(_numbers_simple(_simplify(s, None))))
        if not t:
            continue
        items.append(_highlight_html(t))
        if len(items) >= max_items - (1 if include_normal else 0):
            break
    if include_normal:
        items.append(_highlight_html("Most other areas look normal."))
    if not items:
        items = [_highlight_html("No major problems were seen.")]
    html = "<ul class='ii-list' style='color:#ffffff'>" + "".join(f"<li>{it}</li>" for it in items[:max_items]) + "</ul>"
    return _annotate_terms_outside_tags(html)

# ---------- main API ----------
def build_structured(
    text: str,
    lay_gloss: Glossary | None = None,
    language: str = "English",
    render_style: str = "bullets",
) -> Dict[str, str]:
    meta = parse_metadata(text or "")
    cleaned = _preclean_report(text or "")

    # Clinical History → reason seed
    hx, cleaned = _extract_history(cleaned)
    secs = sections_from_text(cleaned)

    reason_seed = secs.get("reason") or "Not provided."
    if hx:
        reason_seed = (reason_seed.rstrip(".") + f". History: {hx}.").strip()
    findings_src = _strip_signatures(secs.get("findings") or (cleaned or "Not described."))
    impression_src = _strip_signatures(secs.get("impression") or "")

    m = re.search(r"(?mi)^\s*comparison\s*:\s*(.+)$", cleaned)
    comparison = (m.group(1).strip() if m else "")
    m = re.search(r"(?mi)^\s*oral\s+contrast\s*:\s*(.+)$", cleaned)
    oral_contrast = (m.group(1).strip() if m else "")

    # fallbacks
    fallback_findings = _simplify(_prune_findings_for_public(findings_src), lay_gloss)
    base_conc = impression_src or ""
    if not base_conc:
        picks: List[str] = []
        for kw in ["mass","obstruction","compression","dilation","fracture","bleed","appendicitis","adenopathy","necrotic","atrophy"]:
            m2 = re.search(rf"(?is)([^.]*\b{kw}\b[^.]*)\.", cleaned)
            if m2:
                picks.append(m2.group(0).strip())
        base_conc = " ".join(dict.fromkeys(picks))
    fallback_conclusion = _simplify(base_conc or "See important findings.", lay_gloss)

    concern = ""
    for kw in ["obstruction", "compression", "invasion", "perforation", "ischemia"]:
        if re.search(rf"(?i)\b{kw}\b", cleaned):
            concern = f"The findings include {kw}. Discuss next steps with your clinician."
            break

    # LLM attempt
    llm = _summarize_with_openai(cleaned, language)
    llm_reason = _strip_labels(llm.get("reason", "")) if llm else ""
    llm_tech = _strip_labels(llm.get("technique", "")) if llm else ""

    raw_findings = (_simplify(_strip_labels(llm.get("findings","")), lay_gloss) if llm else "") or fallback_findings
    raw_conclusion = (_simplify(_strip_labels(llm.get("conclusion","")), lay_gloss) if llm else "") or fallback_conclusion
    concern_txt = (_simplify(llm.get("concern",""), lay_gloss) if llm else "") or concern

    # Technique: prefer deterministic extraction
    technique_extracted = _extract_technique_details(cleaned) or _infer_modality_and_region(cleaned)
    technique_txt = technique_extracted or _simplify(llm_tech, lay_gloss) or "Technique not described."

    # Reason: inferred and simplified
    reason_txt = _infer_reason(cleaned, llm_reason or reason_seed)

    # render: HTML with white default + colors + tooltips
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
        "name": meta.get("name", ""),
        "age": meta.get("age", ""),
        "sex": meta.get("sex", ""),
        "hospital": meta.get("hospital", ""),
        "date": meta.get("date", ""),
        "study": meta.get("study", ""),
        "reason": reason_html.strip(),           # HTML, white + tooltips
        "technique": technique_html.strip(),     # HTML, white + tooltips; always filled
        "comparison": comparison,
        "oral_contrast": oral_contrast,
        "findings": findings_html.strip(),       # HTML list, red/green + tooltips
        "conclusion": conclusion_html.strip(),   # HTML list, red/green + tooltips
        "concern": concern_html.strip(),
        "word_count": words,
        "sentence_count": sentences,
        "highlights_positive": pos_hi,
        "highlights_negative": neg_hi,
    }

__all__ = ["Glossary", "build_structured"]
