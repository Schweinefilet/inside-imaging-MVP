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
    "metastasis":"spread to other areas","obstruction":"a blockage","compression":"being pressed or squeezed by something","invasion":"growing into nearby tissues",
    "perforation":"a hole or tear","ischemia":"low blood flow","fracture":"a broken bone","bleed":"bleeding","herniation":"disc material pushed out of place",
    "edema":"swelling with fluid buildup","atrophy":"shrinking or wasting of tissue","stenosis":"narrowing of a passage or canal","anomaly":"difference from typical anatomy",
    "mass effect":"pressure on brain structures","subfalcine herniation":"brain shifted under the central fold","midline shift":"brain pushed off center",
    "perilesional edema":"swelling around the lesion",
    # spine-specific
    "disc bulge":"disc cushion pushed out beyond normal boundaries","nerve root":"nerve branch exiting the spinal cord",
    "foraminal narrowing":"smaller space where nerve exits the spine","spinal canal":"tunnel that protects the spinal cord",
    "bilateral":"on both sides","unilateral":"on one side only","posterior":"toward the back","anterior":"toward the front",
    "degenerative":"wear and tear from aging or use","vertebra":"individual spine bone","intervertebral":"between spine bones",
}

# ---------- plain-language rewrites ----------
_JARGON_MAP = [
    (re.compile(r"\bsubfalcine\s+herniation\b", re.I), "subfalcine herniation, brain shift under the central fold"),
    (re.compile(r"\bperilesional\b", re.I), "around the lesion"),
    (re.compile(r"\bparenchymal\b", re.I), "brain tissue"),
    (re.compile(r"\bavid(ly)?\s+enhanc(?:ing|ement)\b|\bavid(ly)?\s+enhacing\b", re.I), "enhances with contrast dye"),
    (re.compile(r"\bhyperintense\b", re.I), "brighter on the scan"),
    (re.compile(r"\bhypointense\b", re.I), "darker on the scan"),
    (re.compile(r"\bhyperdense\b", re.I), "brighter on the scan"),
    (re.compile(r"\bhypodense\b", re.I), "darker on the scan"),
    (re.compile(r"\benhancing\b", re.I), "lighting up after dye"),
    (re.compile(r"\bnon[-\s]?enhancing\b", re.I), "not lighting up after dye"),
    (re.compile(r"\bheterogene(?:ous|ity)\b", re.I), "mixed appearance"),
    (re.compile(r"\bfoci\b", re.I), "spots"),
    (re.compile(r"\bnodular\b", re.I), "lumpy"),
    (re.compile(r"\blesion\b", re.I), "lesion (abnormal area)"),
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
    (re.compile(r"\bischemi(?:a|c)\b", re.I), "low blood flow"),
    (re.compile(r"\bperfusion\b", re.I), "blood flow"),
    (re.compile(r"\bembol(?:us|i|ism)\b", re.I), "blood clot"),
    (re.compile(r"\bstenosis\b", re.I), "narrowing"),
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
    {"pat": r"\bdisc\s+bulge\b", "def": "disc cushion pushed outward beyond normal boundaries"},
    {"pat": r"\bdisc\s+herniation\b", "def": "disc material pushed out of its normal position"},
    {"pat": r"\bforamina?\b", "def": "openings where nerves exit the spinal canal"},
    {"pat": r"\bforaminal\s+narrowing\b", "def": "smaller space where nerve exits, potentially pinching the nerve"},
    {"pat": r"\bnerve\s+root\s+compression\b", "def": "nerve branch being squeezed as it exits the spine"},
    {"pat": r"\bspinal\s+canal\s+stenosis\b", "def": "narrowing of the tunnel that protects the spinal cord"},
    {"pat": r"\bspondylosis\b", "def": "spine wear and tear from aging"},
    {"pat": r"\bosteophyte\b", "def": "bone spur - extra bone growth"},
    {"pat": r"\bcalvarium\b", "def": "skull bones over the brain"},
    {"pat": r"\bvertebral\s+body\b", "def": "main cylindrical part of a spine bone"},
    {"pat": r"\bintervertebral\s+disc\b", "def": "cushion between spine bones"},
    {"pat": r"\bdegenerative\s+change", "def": "wear and tear from normal aging"},
    {"pat": r"\bposterior\b", "def": "toward the back"},
    {"pat": r"\banterior\b", "def": "toward the front"},
    {"pat": r"\bbilateral\b", "def": "on both sides"},
    {"pat": r"\bunilateral\b", "def": "on one side only"},
    {"pat": r"\blumbar\b", "def": "lower back region"},
    {"pat": r"\bcervical\b", "def": "neck region"},
    {"pat": r"\bthoracic\b", "def": "mid-back region"},
    {"pat": r"\bconus\s+medullaris\b", "def": "tapered end of the spinal cord"},
    {"pat": r"\bligamentum\s+flavum\b", "def": "elastic ligament connecting vertebrae"},
    {"pat": r"\bfacet\s+joint\b", "def": "small joint between spine bones"},
    {"pat": r"\buvunjaji\b", "def": "fracture"},
    # commonly missing definitions
    {"pat": r"\bhydroureteronephrosis\b", "def": "swelling of kidney and ureter from blocked urine"},
    {"pat": r"\bhydronephrosis\b", "def": "kidney swelling from blocked urine"},
    {"pat": r"\bhydroureter\b", "def": "ureter swelling from blocked urine"},
    {"pat": r"\badenopathy\b", "def": "swollen lymph nodes"},
    {"pat": r"\bnecrotic\b", "def": "dead tissue"},
    {"pat": r"\bmetastasis\b", "def": "cancer spread to other areas"},
    {"pat": r"\bobstruction\b", "def": "blockage"},
    {"pat": r"\bcompression\b", "def": "being squeezed or pressed"},
    {"pat": r"\binvasion\b", "def": "growth spreading into nearby tissues"},
    {"pat": r"\bperforation\b", "def": "hole or tear in tissue"},
    {"pat": r"\bischemia\b", "def": "reduced blood flow"},
    {"pat": r"\batrophy\b", "def": "tissue shrinking or wasting away"},
    {"pat": r"\bstenosis\b", "def": "narrowing of a passage"},
    # Additional commonly missing medical terms
    {"pat": r"\bparenchyma\b", "def": "the functional tissue of an organ"},
    {"pat": r"\bcortex\b", "def": "the outer layer of an organ"},
    {"pat": r"\bmedulla\b", "def": "the inner part of an organ"},
    {"pat": r"\blumen\b", "def": "the hollow space inside a tube or vessel"},
    {"pat": r"\bmucosa\b", "def": "the moist inner lining of some organs"},
    {"pat": r"\bserosa\b", "def": "the smooth outer lining of organs"},
    {"pat": r"\bcapsule\b", "def": "a membrane enclosing an organ"},
    {"pat": r"\bhilum\b", "def": "the area where vessels enter/exit an organ"},
    {"pat": r"\bfistula\b", "def": "an abnormal connection between two body parts"},
    {"pat": r"\banastomosis\b", "def": "a connection between two vessels or structures"},
    {"pat": r"\bembolism\b", "def": "blockage of a blood vessel by a clot or debris"},
    {"pat": r"\bthrombus\b", "def": "a blood clot inside a vessel"},
    {"pat": r"\baneurysm\b", "def": "a bulge in a blood vessel wall"},
    {"pat": r"\bocclusion\b", "def": "complete blockage of a passage"},
    {"pat": r"\binfarction\b", "def": "tissue death due to lack of blood supply"},
    {"pat": r"\bhemorrhage\b", "def": "bleeding"},
    {"pat": r"\bhematoma\b", "def": "collection of blood outside vessels"},
    {"pat": r"\bcontusion\b", "def": "a bruise"},
    {"pat": r"\blaceration\b", "def": "a cut or tear in tissue"},
    {"pat": r"\brupture\b", "def": "bursting or tearing of an organ or tissue"},
    {"pat": r"\bprolapse\b", "def": "slipping of an organ from its normal position"},
    {"pat": r"\beffusion\b", "def": "fluid buildup in a space"},
    {"pat": r"\bascites\b", "def": "fluid buildup in the belly"},
    {"pat": r"\bedema\b", "def": "swelling from fluid buildup"},
    {"pat": r"\bsplenomegaly\b", "def": "enlarged spleen"},
    {"pat": r"\bhepatomegaly\b", "def": "enlarged liver"},
    {"pat": r"\bcardiomegaly\b", "def": "enlarged heart"},
    {"pat": r"\batelectasis\b", "def": "collapsed lung tissue"},
    {"pat": r"\bpneumothorax\b", "def": "air in the chest cavity causing lung collapse"},
    {"pat": r"\bpleural effusion\b", "def": "fluid around the lung"},
    {"pat": r"\bconsolidation\b", "def": "lung tissue filled with fluid or pus"},
    {"pat": r"\bopacity\b", "def": "an area that blocks X-rays (appears white)"},
    {"pat": r"\blucency\b", "def": "an area that allows X-rays through (appears dark)"},
    {"pat": r"\bcalcification\b", "def": "calcium deposits in tissue"},
    {"pat": r"\bsclerosis\b", "def": "hardening of tissue"},
    {"pat": r"\bfibrosis\b", "def": "scarring"},
    {"pat": r"\bcirrhosis\b", "def": "severe liver scarring"},
    {"pat": r"\bneoplasm\b", "def": "abnormal growth or tumor"},
    {"pat": r"\bmalignancy\b", "def": "cancer"},
    {"pat": r"\bbenign\b", "def": "not cancerous"},
    {"pat": r"\bnodule\b", "def": "a small rounded lump"},
    {"pat": r"\bcyst\b", "def": "a fluid-filled sac"},
    {"pat": r"\babscess\b", "def": "a pocket of pus"},
    {"pat": r"\bgranuloma\b", "def": "a small area of inflammation"},
    {"pat": r"\bpolyp\b", "def": "a growth projecting from a mucous membrane"},
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
_PHI_STOPWORDS = {
    "hospital","clinic","centre","center","medical","radiology","imaging","ct","mri","xray",
    "scan","study","male","female","sex","age","date","mrn","patient","ref","no","number",
    "id","account","acct","doctor","dr","clinic",
}

_PHI_PLACEHOLDER_REPLACEMENTS = {
    "[REDACTED]": "the patient",
    "[DOB]": "date withheld",
    "[AGE]": "age withheld",
    "[SEX]": "sex withheld",
    "[AGE/SEX]": "age/sex withheld",
}


def _phi_term_variants(value: str) -> List[str]:
    terms: List[str] = []
    val = (value or "").strip()
    if not val:
        return terms
    cleaned = re.sub(r"\s+", " ", val)
    if cleaned:
        terms.append(cleaned)
    split_src = re.sub(r"[:;,_-]+", " ", cleaned)
    for piece in split_src.split():
        piece = piece.strip()
        if len(piece) < 2:
            continue
        low = piece.lower()
        if low in _PHI_STOPWORDS:
            continue
        if not re.search(r"[A-Za-z]", piece):
            continue
        terms.append(piece)
    return terms


def _collect_phi_terms(meta: Dict[str, str]) -> List[str]:
    terms: List[str] = []
    for key in ("name", "hospital", "date"):
        val = meta.get(key, "")
        terms.extend(_phi_term_variants(val))
    return [t for t in terms if t]


def _normalize_phi_placeholders(text: str) -> str:
    t = text or ""
    for placeholder, replacement in _PHI_PLACEHOLDER_REPLACEMENTS.items():
        if placeholder in t:
            t = t.replace(placeholder, replacement)
    return t


def _redact_phi(s: str, extra_terms: List[str] | None = None) -> str:
    t = s or ""
    t = re.sub(r"(?im)^\s*(name|patient|pt|mrn|id|acct|account|gender|sex|age|dob|date\s+of\s+birth)\s*[:#].*$","[REDACTED]",t)
    t = re.sub(r"(?i)\bDOB\s*[:#]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b","[DOB]",t)
    t = re.sub(r"(?i)\b(date\s+of\s+birth)\s*[:#]?\s*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b","[DOB]",t)
    t = re.sub(r"(?i)\b(\d{1,3})\s*(?:year[- ]?old|y/o|yo|yrs?|years?)\b","[AGE]",t)
    t = re.sub(r"(?i)\b(?:male|female)\b","[SEX]",t)
    t = re.sub(r"(?i)\b(\d{1,3})\s*/\s*(m|f)\b","[AGE/SEX]",t)
    t = re.sub(r"(?i)\b(\d{1,3})(m|f)\b","[AGE/SEX]",t)
    t = re.sub(r"(?im)^(\s*(indication|reason|history)\s*:\s*)[A-Z][A-Za-z'.-]+(?:\s+[A-Z][A-Za-z'.-]+){0,2},\s*",r"\1",t)
    if extra_terms:
        for term in extra_terms:
            term = (term or "").strip()
            if not term or len(term) < 2:
                continue
            escaped = re.escape(term)
            t = re.sub(rf"(?i){escaped}", "[REDACTED]", t)
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
    env_model = os.getenv("OPENAI_MODEL", "gpt-5")
    chat_fallback = os.getenv("OPENAI_CHAT_FALLBACK", "gpt-4o-mini")
    return (env_model, chat_fallback)

# ---------- OpenAI ----------
def _call_openai_once(report_text: str, language: str, temperature: float, effort: str) -> Dict[str, str] | None:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    env_model, chat_fallback = _resolve_models()

    # Language-specific instructions
    if language.lower() in ["kiswahili", "swahili"]:
        instructions = f"""Wewe ni msaidizi wa kuandika ripoti za uchunguzi wa mwili kwa lugha rahisi. Andika KILA KITU kwa Kiswahili sanifu BILA kuchanganya Kiingereza.
Rudisha JSON object tu yenye: reason, technique, findings, conclusion, concern.
Hadhira ni mtoto wa miaka 10. Tumia sentensi FUPI SANA (maneno 5-8 kwa kila sentensi). Tumia maneno ya kawaida ambayo mtoto anaweza kuelewa.

reason: Eleza KWA NINI uchunguzi ulifanywa (sentensi 1-2 FUPI SANA). Jumuisha dalili za mgonjwa kwa maneno rahisi. Mfano: "Uchunguzi uliagizwa kwa sababu mgonjwa alikuwa na maumivu ya kichwa na kizunguzungu kwa wiki 2."

technique: Eleza JINSI uchunguzi ulivyofanywa (sentensi 3-5) kwa lugha rahisi. Jumuisha:
- Aina gani ya uchunguzi (MRI, CT, X-ray, Ultrasound)
- Sehemu gani ya mwili ilipigiwa picha
- Jinsi picha zilivyochukuliwa (eleza 'axial' = vipande vya kukata kama mkate, 'coronal' = vipande vya mbele-hadi-nyuma, 'sagittal' = vipande vya upande-hadi-upande)
- Kama dawa ya rangi ilitumiwa na kwa nini ('pamoja na rangi' = dawa maalum ilidukuliwa ili kuona viungo vizuri zaidi, 'bila rangi' = hakuna dawa ilihitajika)
- Eneo gani lilipimwa ('kutoka msingi wa fuvu hadi juu' = kutoka chini ya kichwa hadi juu)
Mfano: "Uchunguzi wa MRI wa ubongo ulifanywa. Picha za kukata zilichukuliwa kama kukata mkate. Hakuna dawa ya rangi iliyodukuliwa. Kichwa chote kilipimwa kutoka chini hadi juu."

findings: bullets 2-3 FUPI; conclusion: bullets 1-2 FUPI; concern: sentensi 1 FUPI.
WEKA NAMBA ZOTE kama zilivyo katika ripoti ya asili - USIZIPUNGUZE. Kama ripoti inasema "5.4 x 5.6 x 6.7 cm", weka sawa sawa kama hivo. Kagua tahajia YOTE. Usitumie majina ya kitaalamu au maneno ya kisayansi.
Andika KILA KITU kwa Kiswahili sanifu bila Kiingereza:
- "scan" → "uchunguzi" au "skani"
- "mass" → "uvimbe" au "chungu"
- "normal" → "kawaida"
- "abnormal" → "si kawaida"
- "brain" → "ubongo"
- "liver" → "ini"
- "kidney" → "figo"
- "fracture" → "mfupa umevunjika"
Hakikisha KILA neno ni Kiswahili."""
    else:
        instructions = f"""You summarize medical imaging reports for the public. Write ALL output EXCLUSIVELY in {language} - do not mix languages.
Return ONLY a JSON object with keys: reason, technique, findings, conclusion, concern.
Audience: educated adult who is not a medical professional. Use clear, conversational language. Avoid patronizing tone.

CRITICAL: Extract information from the ACTUAL report provided - DO NOT copy these examples. These are templates showing the style only:

reason: Explain WHY the scan was ordered in 2-3 sentences. Extract from the "Clinical History", "Indication", or "Reason" section of the report. Connect to the patient's actual symptoms/clinical history mentioned in THIS specific report. Be specific and empathetic.
Example STYLE (adapt to actual report): "This MRI scan was ordered to investigate lower back pain that the patient has been experiencing. The goal was to examine the lumbar spine and identify any structural issues causing discomfort."

technique: Explain HOW the scan was performed in 4-6 sentences. Extract from the "Technique", "Procedure", or technical details section. Use analogies where helpful but don't oversimplify. Include:
- What imaging technology was ACTUALLY used according to the report (MRI, CT, X-ray, ultrasound, etc.) and what makes it special
- Which body region was ACTUALLY examined according to the report
- Whether contrast was ACTUALLY used according to the report
- What the technology can reveal that physical examination cannot
Example STYLE (adapt to actual report): "An MRI (Magnetic Resonance Imaging) scan of the lumbar spine was performed using a 0.35 Tesla magnet. This technology uses powerful magnetic fields and radio waves to create detailed cross-sectional images of soft tissues, discs, and nerves. The imaging captured the spine from multiple angles—top-down (axial), side-to-side (sagittal), and front-to-back (coronal)—to build a complete 3D picture. No contrast dye was needed because the natural differences in tissue density provided clear images. This type of scan is especially good at showing disc problems, nerve compression, and spinal canal narrowing that wouldn't be visible on a regular X-ray."

findings: Present 3-5 key findings from the ACTUAL report in clear bullet points. Start with NORMAL findings to provide context, then address abnormalities. Translate complex medical language into simple, clear sentences. Each bullet should be ONE complete sentence.
CRITICAL for findings:
- Simplify complex medical jargon: "hypo-attenuating mass lesion" → "a darker area that appears to be a mass"
- Remove redundant phrases: "noted in the head the patient the pancreas" → "in the head of the pancreas"
- Each bullet point should be clear and standalone - avoid fragments
- Start with normal/reassuring findings, then abnormalities
- Use measurements exactly as stated but explain what they mean
Example STYLE format (use actual findings from the report):
- "Most of the surrounding organs look healthy: the liver, spleen, and kidneys all appear normal."
- "The pancreas shows a mass measuring 4.1 x 5.3 centimeters in the head region (the right side of the pancreas)."
- "The pancreatic duct (drainage tube) is widened to 5.8 millimeters, which suggests blockage downstream."
- "Bile ducts inside and outside the liver are dilated (swollen), indicating that bile flow is being blocked."

conclusion: Summarize the 1-2 most important findings from the ACTUAL "Conclusion" or "Impression" section in 2-4 clear, simple sentences. Avoid medical jargon. Explain what the findings mean in practical terms.
CRITICAL for conclusion:
- Rewrite ALL medical terms in plain language
- Remove garbled phrases like "the patient the" - simplify grammar
- Focus on what matters most to understanding the condition
- Connect findings to likely symptoms or concerns
- Keep sentences short and direct
Example STYLE (adapt to actual report): "The scan shows a mass in the head of the pancreas measuring about 4 centimeters. This mass is blocking both the pancreatic duct (which drains digestive enzymes) and the bile ducts (which drain bile from the liver). The blockage is causing bile ducts to swell throughout the liver. These findings suggest a pancreatic tumor that needs urgent medical attention."

concern: One clear sentence about next steps appropriate for the ACTUAL findings. Avoid alarming language but be honest.
Example STYLE (adapt to actual report): "These findings should be discussed with your doctor to determine whether physical therapy, medication, or other treatments are appropriate."

CRITICAL RULES:
- Extract ALL information from the ACTUAL report provided below - DO NOT use example text
- Read the "Clinical History" or "Indication" section for the reason - extract the ACTUAL condition/symptoms mentioned
- Read the "Procedure"/"Technique" section for how the scan was done - extract ACTUAL details (MRI vs CT, which body part, Tesla strength, contrast usage, etc.)
- Read the "Findings" section for what was discovered - extract ACTUAL anatomical findings
- Read the "Conclusion"/"Impression" for the summary - extract ACTUAL diagnostic conclusions
- SIMPLIFY all medical jargon: "hypo-attenuating" → "darker area", "lesion" → "abnormal area or mass", "upstream dilatation" → "swelling upstream"
- FIX grammatical errors: remove garbled phrases like "the patient the" or "noted mass effect on" - rewrite in clear English
- NO fragments or incomplete sentences - every sentence must be complete and understandable
- KEEP ALL NUMBERS exactly as stated: "5.4 x 5.6 x 6.7 cm" stays "5.4 x 5.6 x 6.7 cm"
- Use medical terms when necessary but ALWAYS explain them in parentheses the same sentence
- Write for an intelligent adult, not a child
- Be empathetic but factual—avoid false reassurance or unnecessary alarm
- If language is "{language}", write EVERYTHING in pure {language} with NO English words mixed in.

REMEMBER: The examples above show STYLE and FORMAT only. You MUST extract content from the ACTUAL report text provided below."""


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

def _clean_kiswahili_text(text: str) -> str:
    """Post-process Kiswahili text to fix common mixed-language issues."""
    if not text:
        return text
    
    # Common English words that slip through → Kiswahili
    replacements = {
        r'\bscan\b': 'uchunguzi',
        r'\bmass\b': 'uvimbe',
        r'\btumor\b': 'uvimbe',
        r'\bnormal\b': 'kawaida',
        r'\babnormal\b': 'si kawaida',
        r'\bbrain\b': 'ubongo',
        r'\bliver\b': 'ini',
        r'\bkidney\b': 'figo',
        r'\bheart\b': 'moyo',
        r'\blungs?\b': 'mapafu',
        r'\bfracture\b': 'mvunjiko',
        r'\bbleed(?:ing)?\b': 'kutokwa na damu',
        r'\bswelling\b': 'uvimbe',
        r'\bpain\b': 'maumivu',
        r'\binflammation\b': 'uvimbe',
        r'\binfection\b': 'maambukizi',
        r'\bct\s+scan\b': 'uchunguzi wa CT',
        r'\bmri\s+scan\b': 'uchunguzi wa MRI',
        r'\bx-ray\b': 'X-ray',
        r'\bultrasound\b': 'uchunguzi wa sauti',
        r'\bfindings?\b': 'matokeo',
        r'\bconclusion\b': 'hitimisho',
        r'\breason\b': 'sababu',
        r'\btechnique\b': 'mbinu',
        r'\bconcern\b': 'wasiwasi',
        r'\bdoctor\b': 'daktari',
        r'\bpatient\b': 'mgonjwa',
        r'\bhospital\b': 'hospitali',
        r'\bthe\b': '',
        r'\band\b': 'na',
        r'\bor\b': 'au',
        r'\bwith\b': 'na',
        r'\bwithout\b': 'bila',
        r'\bin\b': 'ndani ya',
        r'\bon\b': 'juu ya',
        r'\bof\b': 'ya',
        r'\bto\b': 'kwa',
        r'\bfor\b': 'kwa ajili ya',
    }
    
    result = text
    for pattern, replacement in replacements.items():
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    
    # Clean up extra spaces
    result = re.sub(r'\s+', ' ', result).strip()
    
    return result

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
        result = (_merge_runs(runs) if len(runs)>1 else runs[0]) or None
        
        # Post-process for Kiswahili to remove English words
        if result and language.lower() in ["kiswahili", "swahili"]:
            for key in ("reason", "technique", "findings", "conclusion", "concern"):
                if key in result:
                    result[key] = _clean_kiswahili_text(result[key])
        
        return result
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

def _translate_to_kiswahili(text: str, context: str = "") -> str:
    """Translate simple English fallback text to Kiswahili."""
    translations = {
        "The scan was done to check for a mass.": "Uchunguzi ulifanywa kuangalia uvimbe.",
        "The scan was done to look for a problem in the head.": "Uchunguzi ulifanywa kutafuta tatizo katika kichwa.",
        "The scan was done to look for a problem in the neck.": "Uchunguzi ulifanywa kutafuta tatizo katika shingo.",
        "The scan was done to look for a problem in the abdomen.": "Uchunguzi ulifanywa kutafuta tatizo katika tumbo.",
        "The scan was done to look for a problem in the area.": "Uchunguzi ulifanywa kutafuta tatizo katika eneo.",
        " and swollen lymph nodes.": " na lymph nodes zilizovimba.",
        "The goal was to find a simple cause for the symptoms.": "Lengo lilikuwa kupata sababu rahisi ya dalili.",
    "The scan was ordered to investigate a mass.": "Uchunguzi uliagizwa kuchunguza uvimbe.",
    "The scan was ordered to evaluate the head.": "Uchunguzi uliagizwa kuchunguza kichwa.",
    "The scan was ordered to evaluate the neck.": "Uchunguzi uliagizwa kuchunguza shingo.",
    "The scan was ordered to evaluate the abdomen.": "Uchunguzi uliagizwa kuchunguza tumbo.",
    "The scan was ordered to evaluate the area.": "Uchunguzi uliagizwa kuchunguza eneo hili.",
    "Doctors wanted to understand what is causing the current symptoms.": "Madaktari walitaka kuelewa kinachosababisha dalili za sasa.",
        "Technique not described.": "Mbinu haijaeleweshwa.",
        "Not described.": "Haijaeleweshwa.",
        "No major problems were seen.": "Hakuna matatizo makubwa yaliyoonekana.",
        "Most other areas look normal.": "Maeneo mengine yanaonekana kawaida.",
        "See important findings.": "Tazama matokeo muhimu.",
        "CT scan": "Uchunguzi wa CT",
        "MRI": "Uchunguzi wa MRI",
        "Ultrasound": "Uchunguzi wa sauti",
        "X-ray": "X-ray",
        " of the ": " ya ",
        " with contrast.": " na rangi.",
        " without contrast.": " bila rangi.",
    }
    
    result = text
    for eng, swh in translations.items():
        result = result.replace(eng, swh)
    
    return result

def _infer_reason(text: str, seed: str, language: str = "English") -> str:
    src = (seed or "").strip()
    if not src or src.lower() == "not provided.":
        match = re.search(r"(?im)^\s*(indication|reason|history)\s*:\s*(.+)$", text or "")
        if match:
            src = match.group(2).strip()

    cleaned_seed = _strip_labels(src)
    cleaned_seed = re.sub(r"(?i)\b(history|clinical\s+history)\s*:\s*", "", cleaned_seed).strip()

    if cleaned_seed:
        bullets = _normalize_listish(cleaned_seed)
        sentences: List[str] = []
        if bullets:
            for item in bullets[:2]:
                simple = _simplify(item, None)
                if not simple:
                    continue
                simple = simple.strip()
                if simple and not simple.endswith('.'):
                    simple += '.'
                sentences.append(simple)
        else:
            simple = _simplify(cleaned_seed, None)
            if simple:
                simple = simple.strip()
                if simple and not simple.endswith('.'):
                    simple += '.'
                sentences = _split_sentences(simple) or [simple]
        if sentences:
            reason = " ".join(sentences[:2]).strip()
            if language.lower() in ["kiswahili", "swahili"]:
                reason = _clean_kiswahili_text(reason)
            return reason

    low_all = (text or "").lower() + " " + (src or "").lower()

    region = "head" if any(w in low_all for w in ["head","skull","brain"]) else \
             "neck" if "neck" in low_all else \
             "abdomen" if any(w in low_all for w in ["abdomen","abdominal","belly","pancreas","pancreatic","biliary","liver","hepatic","gallbladder"]) else \
             "area"

    has_mass = bool(re.search(r"\b(mass|lesion|tumou?r|nodule|cyst)\b", low_all))
    has_nodes = bool(re.search(r"\b(adenopathy|lymph\s*node|lymphaden)\b", low_all))

    part1 = "The scan was ordered to investigate a mass." if has_mass else f"The scan was ordered to evaluate the {region}."
    if has_nodes:
        part1 = part1.rstrip('.') + " and swollen lymph nodes."
    part2 = "Doctors wanted to understand what is causing the current symptoms."
    fallback = f"{part1} {part2}".strip()

    if language.lower() in ["kiswahili", "swahili"]:
        fallback = _translate_to_kiswahili(fallback)

    return fallback


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

def _to_colored_bullets_html(raw: str, max_items: int, include_normal: bool, language: str = "English") -> str:
    items: List[str] = []
    sources = _normalize_listish(raw) or _split_sentences(raw or "")
    for s in sources:
        s = _drop_heading_labels_line(s)
        t = _tidy_phrases(_grammar_cleanup(_numbers_simple(_simplify(s, None))))
        t = _dedupe_redundant_noun_phrase(t)
        if not t:
            continue
        # Translate to Kiswahili if needed
        if language.lower() in ["kiswahili", "swahili"]:
            t = _clean_kiswahili_text(t)
        items.append(_highlight_phrasewise(t))
        if len(items) >= max_items - (1 if include_normal else 0):
            break
    if include_normal:
        normal_text = "Most other areas look normal."
        if language.lower() in ["kiswahili", "swahili"]:
            normal_text = "Maeneo mengine yanaonekana kawaida."
        items.append(_highlight_phrasewise(normal_text))
    if not items:
        no_problems_text = "No major problems were seen."
        if language.lower() in ["kiswahili", "swahili"]:
            no_problems_text = "Hakuna matatizo makubwa yaliyoonekana."
        items = [_highlight_phrasewise(no_problems_text)]
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

    phi_terms = _collect_phi_terms(meta)
    sanitized_for_model = _redact_phi(cleaned, extra_terms=phi_terms)
    sanitized_for_public = _normalize_phi_placeholders(sanitized_for_model)

    reason_seed = secs.get("reason") or "Not provided."
    if hx: reason_seed = (reason_seed.rstrip(".") + f". History: {hx}.").strip()
    findings_src = _strip_signatures(secs.get("findings") or (cleaned or "Not described."))
    impression_src = _strip_signatures(secs.get("impression") or "")
    findings_src_masked = _normalize_phi_placeholders(_redact_phi(findings_src, extra_terms=phi_terms))
    impression_src_masked = _normalize_phi_placeholders(_redact_phi(impression_src, extra_terms=phi_terms))

    m = re.search(r"(?mi)^\s*comparison\s*:\s*(.+)$", cleaned); comparison = (m.group(1).strip() if m else "")
    m = re.search(r"(?mi)^\s*oral\s+contrast\s*:\s*(.+)$", cleaned); oral_contrast = (m.group(1).strip() if m else "")

    fallback_findings = _simplify(_prune_findings_for_public(findings_src_masked), lay_gloss)
    base_conc = impression_src_masked or ""
    if not base_conc:
        picks: List[str] = []
        search_source = sanitized_for_public or cleaned
        for kw in ["mass","obstruction","compression","dilation","fracture","bleed","appendicitis","adenopathy","necrotic","atrophy","stenosis","herniation"]:
            m2 = re.search(rf"(?is)([^.]*\b{kw}\b[^.]*)\.", search_source)
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
    llm = _summarize_with_openai(sanitized_for_model, language)
    llm_reason = _strip_labels((llm or {}).get("reason","")) if llm else ""
    llm_tech = _strip_labels((llm or {}).get("technique","")) if llm else ""

    raw_findings = (_simplify(_strip_labels((llm or {}).get("findings","")), lay_gloss) if llm else "") or fallback_findings
    raw_conclusion = (_simplify(_strip_labels((llm or {}).get("conclusion","")), lay_gloss) if llm else "") or fallback_conclusion
    raw_findings = _normalize_phi_placeholders(raw_findings)
    raw_conclusion = _normalize_phi_placeholders(raw_conclusion)

    # remove overlap
    raw_findings, raw_conclusion = _dedupe_sections(raw_findings, raw_conclusion)

    concern_txt = (_simplify((llm or {}).get("concern",""), lay_gloss) if llm else "") or concern
    concern_txt = _normalize_phi_placeholders(concern_txt)

    # technique prefer deterministic
    technique_extracted = _extract_technique_details(cleaned) or _infer_modality_and_region(cleaned)
    technique_txt = technique_extracted or _simplify(llm_tech, lay_gloss) or "Technique not described."
    
    # Translate technique fallback to Kiswahili if needed
    if language.lower() in ["kiswahili", "swahili"] and technique_txt == "Technique not described.":
        technique_txt = "Mbinu haijaeleweshwa."
    elif language.lower() in ["kiswahili", "swahili"]:
        technique_txt = _translate_to_kiswahili(technique_txt)

    # reason
    reason_txt = _infer_reason(cleaned, llm_reason or reason_seed, language)
    reason_txt = _normalize_phi_placeholders(reason_txt)
    technique_txt = _normalize_phi_placeholders(technique_txt)

    # render
    findings_html = _to_colored_bullets_html(raw_findings, max_items=4, include_normal=True, language=language)
    conclusion_html = _to_colored_bullets_html(raw_conclusion, max_items=2, include_normal=False, language=language)
    reason_html = _annotate_terms_outside_tags(f'<span class="ii-text" style="color:#ffffff">{_simplify(reason_txt, lay_gloss)}</span>')
    technique_html = _annotate_terms_outside_tags(f'<span class="ii-text" style="color:#ffffff">{_simplify(technique_txt, lay_gloss)}</span>')
    concern_html = _annotate_terms_outside_tags(f'<span class="ii-text" style="color:#ffffff">{_simplify(concern_txt, lay_gloss)}</span>') if concern_txt else ""

    # stats
    words = len(re.findall(r"\w+", cleaned or ""))
    sentences = len(re.findall(r"[.!?]+", cleaned or ""))
    pos_hi = len(re.findall(r'class="ii-pos"', findings_html + conclusion_html))
    neg_hi = len(re.findall(r'class="ii-neg"', findings_html + conclusion_html))

    patient_bundle = {
        "name": meta.get("name", ""),
        "age": meta.get("age", ""),
        "sex": meta.get("sex", ""),
        "hospital": meta.get("hospital", ""),
        "date": meta.get("date", ""),
        "study": meta.get("study", ""),
        "history": hx,
    }

    return {
        "name": patient_bundle.get("name", ""), "age": patient_bundle.get("age", ""), "sex": patient_bundle.get("sex", ""),
        "hospital": patient_bundle.get("hospital", ""), "date": patient_bundle.get("date", ""), "study": patient_bundle.get("study", ""),
        "reason": reason_html.strip(), "technique": technique_html.strip(),
        "comparison": comparison or "None", "oral_contrast": oral_contrast or "Not stated",
        "findings": findings_html.strip(), "conclusion": conclusion_html.strip(), "concern": concern_html.strip(),
        "word_count": words, "sentence_count": sentences, "highlights_positive": pos_hi, "highlights_negative": neg_hi,
        "patient": patient_bundle,
    }

__all__ = ["Glossary", "build_structured"]
