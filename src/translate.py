# src/translate.py
from __future__ import annotations

import csv, re, os, json, logging, html as _html
from dataclasses import dataclass
from typing import Dict, List, Callable, Tuple

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

# --- cleaners --------------------------------------------------------
def _preclean_report(raw: str) -> str:
    if not raw:
        return ""
    s = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.strip() for ln in s.split("\n")]

    start_rx = re.compile(
        r"(?i)\b(history|indication|reason|technique|procedure|findings?|impression|conclusion|"
        r"report|scan|mri|ct|ultrasound|usg|axial|cect|nect)\b"
    )
    start = 0
    for i, ln in enumerate(lines):
        if start_rx.search(ln):
            start = i
            break
    lines = lines[start:]

    drop_exact = re.compile(r"(?i)^(report|summary|x-?ray|ct\s+head|ct\s+brain)$")
    drop_keyval = re.compile(r"(?i)^\s*(ref(\.|:)?\s*no|ref|date|name|age|sex|mrn|id|file|account|acct)\s*[:#].*$")

    def _is_caps_banner(ln: str) -> bool:
        if len(ln) <= 2:
            return False
        if len(ln.split()) > 8:
            return False
        return bool(re.match(r"^[A-Z0-9 &/.-]+$", ln)) and not re.search(r"\b(MRI|CT|US|XR)\b", ln)

    kept: List[str] = []
    for ln in lines:
        if not ln:
            continue
        if drop_exact.match(ln):
            continue
        if drop_keyval.match(ln):
            continue
        if _is_caps_banner(ln):
            continue
        kept.append(ln)

    cleaned: List[str] = []
    for ln in kept:
        if cleaned and cleaned[-1] == ln:
            continue
        cleaned.append(ln)
    return "\n".join(cleaned)

def _strip_signatures(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"(?im)^\s*(dr\.?.*|consultant\s*radiologist.*|radiologist.*|dictated\s+by.*)\s*$", "", s)
    s = re.sub(r"(?im)^\s*(signed|electronically\s+signed.*)\s*$", "", s)
    return s.strip()

def _unwrap_soft_breaks(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"-\s*\n(?=\w)", "", s)
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"(?<!\n)\n(?!\n)", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s

def _grammar_cleanup(text_only: str) -> str:
    s = text_only
    s = re.sub(r"\bare looks\b", "look", s, flags=re.I)
    s = re.sub(r"\bis looks\b", "looks", s, flags=re.I)
    s = re.sub(r"\bare appears?\b", "appear", s, flags=re.I)
    s = re.sub(r"\bis appear\b", "appears", s, flags=re.I)
    s = re.sub(r"\bstructures are look(s)?\b", "structures look", s, flags=re.I)
    s = re.sub(r"\s{2,}", " ", s)
    return s

# ---------- helpers ---------------------------------------------------
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

# ---------- LLM summarizer -------------------------------------------
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
You are a medical report summarizer for the public.
Write all output in {language}.
Return ONLY a JSON object with keys: reason, technique, findings, conclusion, concern.
Audience is a 13-year-old. Short sentences.

Use plain words. Bold core diagnosis terms once.
reason and technique: 2–4 sentences each; findings and conclusion: 3–6; concern: 2–4.
Round numbers. Use cm unless under 1 cm, then mm.
Findings: bullet list, 3–5 bullets, 4–8 words each, start with **bolded key phrase**, collapse normals to one bullet.
Conclusion: 1–2 bullets, 5–9 words. Plain words.
No names. No extra keys.
""".strip()

        json_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "reason": {"type": "string"},
                "technique": {"type": "string"},
                "findings": {"type": "string"},
                "conclusion": {"type": "string"},
                "concern": {"type": "string"},
            },
            "required": ["reason", "technique", "findings", "conclusion", "concern"],
        }

        # Build base kwargs WITHOUT temperature (unsupported on some new models)
        base_kwargs = dict(
            model=model,
            instructions=instructions,
            input=report_text,
            max_output_tokens=2000,
        )

        # Try structured output first; some SDKs don’t support response_format
        try:
            resp = client.responses.create(
                **base_kwargs,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "public_summary", "schema": json_schema, "strict": True},
                },
            )
        except TypeError as e:
            if "response_format" in str(e):
                resp = client.responses.create(**base_kwargs)
            else:
                raise
        except Exception as e:
            msg = str(e).lower()
            if "response_format" in msg or "unsupported parameter" in msg and "response_format" in msg:
                resp = client.responses.create(**base_kwargs)
            else:
                raise

        # Extract text from Responses API
        text = getattr(resp, "output_text", None)
        if not text:
            try:
                text = resp.output[0].content[0].text.value
            except Exception:
                text = str(resp)
        data = _extract_json_loose(text) or {}

        # Legacy fallback only if model actually supports Chat Completions
        if not data and _supports_chat_completions(model):
            resp2 = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": report_text},
                ],
                max_tokens=1400,
                response_format={"type": "json_object"},
            )
            data = _extract_json_loose(resp2.choices[0].message.content) or {}

        out = {}
        for k in ("reason", "technique", "findings", "conclusion", "concern"):
            v = data.get(k, "")
            out[k] = v.strip() if isinstance(v, str) else str(v or "")
        return out
    except Exception:
        logger.exception("[LLM] summarization failed")
        return None

# ---------- glossary --------------------------------------------------
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

# --- sentiment/highlight words ---------------------------------------
POS_WORDS = [
    "normal","benign","unremarkable","no ","none","clear","symmetric","intact","not enlarged","stable","improved"
]
NEG_WORDS = [
    "mass","tumor","cancer","lesion","adenopathy","enlarged","necrotic","metastasis","obstruction","compression",
    "invasion","perforation","ischemia","fracture","bleed","hydroureteronephrosis","hydroureter","hydronephrosis",
    "herniation","shift","edema","atrophy"
]

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

# ----------- simple-term rewrites for public --------------------------
SIMPLE_PUBLIC_MAP: List[Tuple[re.Pattern, str]] = [
    (re.compile(r"\bvesico[-\s]?ureter(ic|al)\b", re.I), "bladder entrance"),
    (re.compile(r"\bhydroureters?\b", re.I), "urine tube widened"),
    (re.compile(r"\bhydronephrosis\b", re.I), "kidney swelling"),
    (re.compile(r"\brenal\b", re.I), "kidney"),
    (re.compile(r"\bureter\b", re.I), "urine tube"),
    (re.compile(r"\bcalculi\b", re.I), "stones"),
    (re.compile(r"\bcalculus\b", re.I), "stone"),
    (re.compile(r"\bphleboliths?\b", re.I), "small vein calcifications"),
    (re.compile(r"\binterhemispheric\s+fissure\b", re.I), "middle groove"),
    (re.compile(r"\bcerebrum\b", re.I), "brain"),
    (re.compile(r"\bcerebellum\b", re.I), "back of brain"),
    (re.compile(r"\bventricles?\b", re.I), "fluid spaces"),
    (re.compile(r"\bcortical\s+sulcation\b", re.I), "brain surface grooves"),
    (re.compile(r"\bcalvarium\b", re.I), "skull"),
    (re.compile(r"\bintracranial\s+pressure\b", re.I), "brain pressure"),
    (re.compile(r"\batrophy\b", re.I), "brain shrinkage"),
]

def _rewrite_simple_terms(s: str) -> str:
    out = s or ""
    for rx, repl in SIMPLE_PUBLIC_MAP:
        out = rx.sub(repl, out)
    return re.sub(r"\s{2,}", " ", out).strip()

def _enforce_simple_bullets(s: str, max_words: int = 9) -> str:
    if not s:
        return ""
    lines = s.splitlines()
    out: List[str] = []
    for ln in lines:
        if ln.lstrip().startswith(("-", "•")):
            head, rest = ln.split("-", 1) if "-" in ln else ("", ln)
            words = rest.strip().split()
            out.append(f"- {' '.join(words[:max_words])}")
        else:
            out.append(ln)
    return "\n".join(out)

# --- term bank (long > short first) ----------------------------------
_TERM_DEFS = [
    {"pat": r"\bcontrast[-\s]?enhanced\s+ct\b|\bcect\b", "def": "CT with injected contrast dye"},
    {"pat": r"\bnon[-\s]?contrast\s+ct\b|\bnect\b", "def": "CT without contrast dye"},
    {"pat": r"\bcontrast[-\s]?enhanced\s+mri\b", "def": "MRI after contrast dye"},
    {"pat": r"\bgadolinium\b", "def": "contrast dye used for MRI"},
    {"pat": r"\baxial\s+scans?\b|\baxial\b", "def": "slices taken horizontally"},
    {"pat": r"\bcoronal\b", "def": "slices taken front to back"},
    {"pat": r"\bsagittal\b", "def": "slices taken side to side"},
    {"pat": r"\bbrain\s+window\b", "def": "CT display settings for brain tissue"},
    {"pat": r"\bbone\s+window\b", "def": "CT display settings for bone"},
    {"pat": r"\bbase\s+of\s+skull\b|\bskull\s+base\b", "def": "bottom part of the skull"},
    {"pat": r"\bvertex\b", "def": "top of the skull"},
    {"pat": r"\bforamen\s+magnum\b", "def": "large hole where the spinal cord exits the skull"},
    {"pat": r"\bclivus\b", "def": "slope of bone in the skull base"},
    {"pat": r"\bpetrous\s+apex\b", "def": "tip of the hard bone near the inner ear"},
    {"pat": r"\bmeckel'?s\s+cave\b", "def": "small space for a facial nerve branch"},
    {"pat": r"\bcavernous\s+sinus\b", "def": "venous channel beside the pituitary"},
    {"pat": r"\btentorium\b|\btentorial\b", "def": "tough fold separating top and back of brain"},
    {"pat": r"\bfalx\b|\binterhemispheric\s+fissure\b", "def": "central fold and groove between brain halves"},
    {"pat": r"\bcalvarium\b|\bcalvaria\b", "def": "skull cap bones"},
    {"pat": r"\bfronto[-\s]?parietal\b", "def": "where the frontal and parietal lobes meet"},
    {"pat": r"\bfrontal\s+lobe\b", "def": "front part of the brain"},
    {"pat": r"\bparietal\s+lobe\b", "def": "top side part of the brain"},
    {"pat": r"\btemporal\s+lobe\b", "def": "side part near the ears"},
    {"pat": r"\boccipital\s+lobe\b", "def": "back part for vision"},
    {"pat": r"\bextra[-\s]?axial\b", "def": "outside brain tissue but inside the skull"},
    {"pat": r"\bintra[-\s]?axial\b", "def": "inside brain tissue itself"},
    {"pat": r"\bparasellar\b", "def": "next to the sella and pituitary"},
    {"pat": r"\bsuprasellar\b", "def": "above the pituitary"},
    {"pat": r"\bparasagittal\b", "def": "near the middle line"},
    {"pat": r"\bcerebellopontine\s+angle\b|\bcpa\b", "def": "area between cerebellum and brainstem"},
    {"pat": r"\bgreater\s+sphenoid\s+wing\b|\bsphenoid\s+wing\b", "def": "part of skull bone near the temple"},
    {"pat": r"\bcerebral\s+ventricles\b|\bventricles?\b", "def": "fluid-filled spaces inside the brain"},
    {"pat": r"\blateral\s+ventricles?\b", "def": "large side fluid spaces in the brain"},
    {"pat": r"\bthird\s+ventricle\b", "def": "middle fluid space in the brain"},
    {"pat": r"\bfourth\s+ventricle\b", "def": "fluid space between brainstem and cerebellum"},
    {"pat": r"\bbasal\s+cisterns\b", "def": "fluid spaces at the base of the brain"},
    {"pat": r"\bsubarachnoid\s+space(s)?\b", "def": "fluid space around the brain under its lining"},
    {"pat": r"\bcisterna\s+magna\b", "def": "large fluid space behind the cerebellum"},
    {"pat": r"\btransependymal\s+flow\b", "def": "fluid leaking through ventricle lining"},
    {"pat": r"\bhydrocephalus\b", "def": "too much fluid causing big ventricles"},
    {"pat": r"\bcommunicating\s+hydrocephalus\b", "def": "fluid buildup with open flow paths"},
    {"pat": r"\bnon[-\s]?communicating\s+hydrocephalus\b", "def": "fluid buildup due to a blockage"},
    {"pat": r"\bsulci\b|\bsulcus\b", "def": "grooves on the brain surface"},
    {"pat": r"\bgyri\b|\bgyrus\b", "def": "ridges on the brain surface"},
    {"pat": r"\bcortical\s+sulcation\b", "def": "pattern of folds and grooves on the brain"},
    {"pat": r"\bgrey[-\s]?white\s+matter\s+differentiation\b", "def": "normal contrast between outer grey and inner white layers"},
    {"pat": r"\beffaced?\b|\beffacement\b", "def": "thinned or pressed so it looks reduced"},
    {"pat": r"\bdilated?\b|\bdilatation\b|\bdilation\b", "def": "wider than normal"},
    {"pat": r"\bbasal\s+ganglia\b", "def": "deep clusters helping control movement"},
    {"pat": r"\binternal\s+capsule\b", "def": "major nerve fiber pathway"},
    {"pat": r"\bcorpus\s+callosum\b", "def": "thick band connecting brain halves"},
    {"pat": r"\bthalamus\b", "def": "relay center for sensory signals"},
    {"pat": r"\bbrain\s?stem\b|\bbrainstem\b", "def": "connects brain to spinal cord"},
    {"pat": r"\bposterior\s+fossa\b", "def": "back lower skull space holding cerebellum and brainstem"},
    {"pat": r"\bcerebellum\b", "def": "helps balance and coordination"},
    {"pat": r"\btonsillar\s+ectopia\b|\bchiari\b", "def": "lowering of cerebellar tonsils"},
    {"pat": r"\bsella(\s+turcica)?\b", "def": "small bone pocket under the brain that holds the pituitary"},
    {"pat": r"\bpituitary(\s+gland)?\b", "def": "small hormone gland under the brain"},
    {"pat": r"\boptic\s+chiasm\b", "def": "where the optic nerves cross"},
    {"pat": r"\bpituitary\s+stalk\b|\binfundibulum\b", "def": "thin connector between pituitary and brain"},
    {"pat": r"\borbits\b", "def": "eye sockets"},
    {"pat": r"\bglobe\b", "def": "eyeball"},
    {"pat": r"\bextraocular\s+muscles\b", "def": "muscles that move the eyes"},
    {"pat": r"\bparanasal\s+sinuses\b|\bsinuses\b", "def": "air pockets in the face"},
    {"pat": r"\bmastoid\s+air\s+cells\b", "def": "air spaces in bone behind the ear"},
    {"pat": r"\bpneumatized\b|\bpneumatised\b", "def": "normally filled with air"},
    {"pat": r"\bmucosal\s+thickening\b", "def": "lining of the sinus is swollen"},
    {"pat": r"\bair[-\s]?fluid\s+level\b", "def": "air with fluid line, often from infection"},
    {"pat": r"\bopacified\b|\bopacification\b", "def": "looks filled in or not clear"},
    {"pat": r"\blesion\b", "def": "abnormal spot or area"},
    {"pat": r"\bmeningioma\b", "def": "tumor from the brain’s lining"},
    {"pat": r"\bglioma\b|\bastrocytoma\b|\boglioblastoma\b", "def": "tumor from brain tissue"},
    {"pat": r"\bmetastasis\b|\bmetastases\b", "def": "cancer spread from elsewhere"},
    {"pat": r"\bschwannoma\b|\bvestibular\s+schwannoma\b|\bacoustic\s+neuroma\b", "def": "tumor of the balance/hearing nerve"},
    {"pat": r"\bpituitary\s+adenoma\b", "def": "common benign pituitary tumor"},
    {"pat": r"\bcraniopharyngioma\b", "def": "tumor near the pituitary region"},
    {"pat": r"\bepidermoid\b|\bdermoid\b", "def": "growth from skin-like cells"},
    {"pat": r"\bcolloid\s+cyst\b", "def": "gel-filled cyst near the third ventricle"},
    {"pat": r"\bcavernous\s+malformation\b|\bcavernoma\b", "def": "cluster of abnormal blood vessels"},
    {"pat": r"\bavid(ly)?\s+enhanc(ing|ement)\b", "def": "shows strong contrast uptake"},
    {"pat": r"\bheterogeneous\b", "def": "mixed look inside"},
    {"pat": r"\bhomogeneous\b", "def": "even look inside"},
    {"pat": r"\bring[-\s]?enhancing\b", "def": "contrast makes a ring around it"},
    {"pat": r"\bcentral\s+necrosis\b|\bnecrotic\b", "def": "dead tissue in the middle"},
    {"pat": r"\bcalcifications?\b", "def": "small calcium deposits"},
    {"pat": r"\bfat\s+attenuation\b|\bfat\s+signal\b", "def": "looks like fat on scan"},
    {"pat": r"\bcystic\b|\bcyst\b", "def": "fluid-filled area"},
    {"pat": r"\bmass\s+effect\b", "def": "pressure or shift caused by a mass"},
    {"pat": r"\bmidline\s+shift\b", "def": "brain pushed off center"},
    {"pat": r"\bsubfalcine\s+herniation\b", "def": "brain pushed under the central fold"},
    {"pat": r"\buncal\s+herniation\b", "def": "inner temporal lobe pushed over the tentorium"},
    {"pat": r"\btonsillar\s+herniation\b", "def": "cerebellum pushed down through skull opening"},
    {"pat": r"\bperilesional\s+edema\b", "def": "swelling around a lesion"},
    {"pat": r"\bedema\b|\boedema\b", "def": "swelling"},
    {"pat": r"\bvasogenic\s+edema\b", "def": "swelling from leaky vessels"},
    {"pat": r"\bcytotoxic\s+edema\b", "def": "swelling from injured cells"},
    {"pat": r"\bhypodense\b|\bhypoattenuat(e|ion)\b", "def": "darker than normal on CT"},
    {"pat": r"\bhyperdense\b|\bhyperattenuat(e|ion)\b", "def": "brighter than normal on CT"},
    {"pat": r"\bisodense\b", "def": "similar brightness on CT"},
    {"pat": r"\bT1\s*hyperintens(e|ity)\b", "def": "brighter than normal on T1 MRI"},
    {"pat": r"\bT2\s*hyperintens(e|ity)\b", "def": "brighter than normal on T2 MRI"},
    {"pat": r"\bFLAIR\b", "def": "MRI setting that highlights fluid changes"},
    {"pat": r"\bepidural\s+hematoma\b|\bEDH\b", "def": "bleed between skull and outer covering"},
    {"pat": r"\bsubdural\s+hematoma\b|\bSDH\b", "def": "bleed under the outer covering"},
    {"pat": r"\bsubarachnoid\s+hemorrhage\b|\bSAH\b", "def": "bleed in the fluid space around the brain"},
    {"pat": r"\bintra[-\s]?parenchymal\s+hemorrhage\b|\bIPH\b", "def": "bleed inside brain tissue"},
    {"pat": r"\bintra[-\s]?ventricular\s+hemorrhage\b|\bIVH\b", "def": "bleed into the ventricles"},
    {"pat": r"\bcontusion\b", "def": "bruise in the brain"},
    {"pat": r"\bdiffuse\s+axonal\s+injury\b|\bDAI\b", "def": "widespread shearing injury"},
    {"pat": r"\babscess\b", "def": "pocket of infection and pus"},
    {"pat": r"\bencephalitis\b", "def": "inflammation of the brain"},
    {"pat": r"\bmeningitis\b", "def": "infection of the brain’s lining"},
    {"pat": r"\bemp(y|i)ema\b", "def": "collection of pus in a space"},
    {"pat": r"\ban(teri|)or\s+cerebral\s+artery\b|\bACA\b", "def": "front brain artery"},
    {"pat": r"\bmiddle\s+cerebral\s+artery\b|\bMCA\b", "def": "side brain artery"},
    {"pat": r"\bposterior\s+cerebral\s+artery\b|\bPCA\b", "def": "back brain artery"},
    {"pat": r"\baneurysm\b", "def": "bulge in a blood vessel wall"},
    {"pat": r"\bvenous\s+sinus\s+thrombosis\b", "def": "clot in a brain vein channel"},
    {"pat": r"\bwatershed\b", "def": "border-zone area between artery territories"},
    {"pat": r"\bfocal\b", "def": "limited to a small area"},
    {"pat": r"\bdiffuse\b", "def": "spread out widely"},
    {"pat": r"\bmultifocal\b", "def": "in several spots"},
    {"pat": r"\bdominant\s+lesion\b", "def": "largest or main abnormal area"},
    {"pat": r"\bconfluent\b", "def": "areas that run together"},
    {"pat": r"\batrophy\b", "def": "shrinking of tissue"},
    {"pat": r"\bencephalomalacia\b", "def": "softened scarred brain tissue after injury"},
    {"pat": r"\bencephalopathy\b", "def": "general brain dysfunction"},
    {"pat": r"\bcervical\s+lordosis\b", "def": "natural inward curve of the neck"},
    {"pat": r"\bhypolordosis\b|\bloss\s+of\s+lordosis\b|\bstraightening\b", "def": "reduced or straightened neck curve"},
    {"pat": r"\bkyphosis\b", "def": "outward spine curve"},
    {"pat": r"\bscoliosis\b", "def": "sideways spine curve"},
    {"pat": r"\bvertebral\s+bodies?\b", "def": "block-shaped bones of the spine"},
    {"pat": r"\bendplates?\b", "def": "top and bottom surfaces of a vertebra"},
    {"pat": r"\bmodic\s+changes?\b", "def": "types of bone marrow changes at endplates"},
    {"pat": r"\bschmorl'?s?\s+nodes?\b", "def": "small disc herniations into the bone"},
    {"pat": r"\bosteophytes?\b", "def": "bone spurs"},
    {"pat": r"\bspondylosis\b", "def": "wear-and-tear spine changes"},
    {"pat": r"\bspondylolisthesis\b", "def": "one vertebra slipped over another"},
    {"pat": r"\banterolisthesis\b", "def": "forward slip of a vertebra"},
    {"pat": r"\bretrolisthesis\b", "def": "backward slip of a vertebra"},
    {"pat": r"\bspondylolysis\b|\bpars\s+defect\b", "def": "stress fracture in the arch of a vertebra"},
    {"pat": r"\bintervertebral\s+discs?\b|\bdiscs?\b", "def": "soft cushions between vertebrae"},
    {"pat": r"\bdisc\s+bulge\b", "def": "broad shallow extension of the disc"},
    {"pat": r"\bdisc\s+protrusion\b", "def": "focal herniation with a wide base"},
    {"pat": r"\bdisc\s+extrusion\b", "def": "focal herniation with a narrow neck"},
    {"pat": r"\bdisc\s+sequestration\b", "def": "free fragment of disc material"},
    {"pat": r"\bdisc\s+herniation\b", "def": "disc material pushed out of place"},
    {"pat": r"\bannular\s+tear\b|\bannular\s+fissure\b", "def": "small tear in the disc’s outer ring"},
    {"pat": r"\bspinal\s+canal\s+stenosis\b|\bcentral\s+canal\s+stenosis\b|\bcanal\s+stenosis\b", "def": "narrowing of the main canal for the cord"},
    {"pat": r"\bforaminal\s+stenosis\b|\bneural\s+foraminal\s+narrowing\b", "def": "narrowing of nerve exit openings"},
    {"pat": r"\bneuroforamina\b|\bneural\s+foramina\b", "def": "openings where nerves exit"},
    {"pat": r"\buncovertebral\s+joints?\b|\bjoints?\s+of\s+luschka\b", "def": "small side joints in the neck spine"},
    {"pat": r"\bfacet\s+joint(s)?\b|\bfacet\s+arthropathy\b", "def": "joints at the back of the spine (wear changes)"},
    {"pat": r"\bfacet\s+effusion\b", "def": "fluid in a facet joint"},
    {"pat": r"\bligamentum\s+flavum\s+hypertrophy\b", "def": "thickening of a supporting ligament"},
    {"pat": r"\bepidural\s+lipomatosis\b", "def": "too much fat around the canal"},
    {"pat": r"\btarlov\s+cyst(s)?\b|\bperineural\s+cyst(s)?\b", "def": "fluid sacs near nerve roots"},
    {"pat": r"\bspinal\s+cord\b|\bcord\b", "def": "bundle of nerves in the canal"},
    {"pat": r"\bcord\s+compression\b", "def": "pressure on the spinal cord"},
    {"pat": r"\bmyelomalacia\b", "def": "softening or damage of the cord"},
    {"pat": r"\bT2\s*hyperintensit(y|ies)\b", "def": "bright signal on T2 MRI"},
    {"pat": r"\bradiculopath(y|ies)\b|\bradicular\b", "def": "irritation of a nerve root"},
    {"pat": r"\bmyelopath(y|ies)\b", "def": "spinal cord dysfunction"},
    {"pat": r"\bconus\s+medullaris\b", "def": "lower tip of the spinal cord"},
    {"pat": r"\bcauda\s+equina\b", "def": "bundle of nerves below the cord"},
    {"pat": r"\bsyrinx\b|\bsyringomyelia\b", "def": "fluid cavity in the spinal cord"},
    {"pat": r"\blinear\s+fracture\b", "def": "thin crack in bone"},
    {"pat": r"\bdepressed\s+fracture\b", "def": "bone pushed inward"},
    {"pat": r"\bdiastatic\s+fracture\b", "def": "fracture widening a skull suture"},
    {"pat": r"\bpneumocephalus\b", "def": "air inside the skull"},
    {"pat": r"\bmotion\s+artifact\b", "def": "blurring from movement during the scan"},
    {"pat": r"\bbeam[-\s]?hardening\b", "def": "streaks on CT from very dense objects"},
    {"pat": r"\bsusceptibility\s+artifact\b", "def": "MRI distortion from metal or air"},
    {"pat": r"\bintracranial\b", "def": "inside the skull"},
    {"pat": r"\bparenchymal\b", "def": "within the brain tissue"},
    {"pat": r"\bmeninges?\b|\bmeningeal\b", "def": "protective layers around brain and cord"},
    {"pat": r"\btumou?r\b", "def": "a growth that forms a lump"},
    {"pat": r"\bmalignan(t|cy)\b", "def": "cancerous"},
    {"pat": r"\bbenign\b", "def": "not cancer"},
]

_SIMPLE_MAP = [
    (r"\bunremarkable\b", "looks normal"),
    (r"\bintact\b", "normal"),
    (r"\bsymmetric\b", "same on both sides"),
    (r"\bbenign\b", "not dangerous"),
]

# Precompile term regexes once
_TERM_REGEX: List[Tuple[re.Pattern, str]] = [(re.compile(d["pat"], re.I), d["def"]) for d in _TERM_DEFS]

# ---------- organ links ----------------------------------------------
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
_org_keys_sorted = sorted(_ORGAN_MAP.keys(), key=len, reverse=True)
_ORG_RX = re.compile(r"(?i)\b(" + "|".join(re.escape(k) for k in _org_keys_sorted) + r")\b")

# ---------- safe text-only transformer -------------------------------
def _map_text_outside_tags(s: str, fn: Callable[[str], str]) -> str:
    if not s:
        return ""
    parts = re.split(r"(<[^>]+>)", s)
    for i in range(0, len(parts), 2):
        parts[i] = fn(parts[i])
    return "".join(parts)

def _escape_attr(s: str) -> str:
    return _html.escape(s or "", quote=True)

# ---------- transformers ---------------------------------------------
def _link_organs_plain(text_only: str) -> str:
    def _rep(m: re.Match) -> str:
        t = m.group(0)
        key = _ORGAN_MAP.get(t.lower(), t.lower())
        return f'<span class="organ-link" data-organ="{_html.escape(key)}">{_html.escape(t)}</span>'
    return _ORG_RX.sub(_rep, text_only)

def _link_organs_safe(s: str) -> str:
    return _map_text_outside_tags(s, _link_organs_plain)

def _simplify_language(text_only: str) -> str:
    out = text_only
    for pat, repl in _SIMPLE_MAP:
        out = re.sub(pat, repl, out, flags=re.I)
    return out

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
        out.append(f'<span class="term-def" data-def="{_escape_attr(d)}">{_html.escape(vis)}</span>')
        pos = e
    out.append(text_only[pos:])
    return "".join(out)

def _mark_highlights(text_only: str) -> str:
    out = text_only
    for w in POS_WORDS:
        if w.endswith(" "):
            out = re.sub(rf"(?i)(?<!\w){re.escape(w.strip())}\s+\w+", lambda m: f"**{m.group(0)}**", out)
        else:
            out = re.sub(rf"(?i)\b{re.escape(w)}\b", lambda m: f"**{m.group(0)}**", out)
    for w in NEG_WORDS:
        out = re.sub(rf"(?i)\b{re.escape(w)}\b", lambda m: f"**{m.group(0)}**", out)
    return out

def _numbers_simple(text_only: str) -> str:
    def _round(m: re.Match) -> str:
        num = m.group(0)
        try:
            f = float(num)
            if abs(f) >= 10:
                return str(int(round(f)))
            return f"{round(f, 1):g}"
        except Exception:
            return num
    s2 = re.sub(r"(?<!\w)(\d+\.\d+|\d+)(?!\w)", _round, text_only)
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

def _convert_highlights(htmlish: str) -> str:
    if not htmlish:
        return ""
    def classify(m: re.Match) -> str:
        txt = m.group(1)
        low = txt.lower()
        is_pos = any(p in low for p in ["no ", "without", " not "]) or any(p in low for p in POS_WORDS)
        is_neg = any(k in low for k in NEG_WORDS)
        if is_pos and not is_neg:
            return f'<strong class="positive">{_html.escape(txt)}</strong>'
        if is_neg and not is_pos:
            term = next((w for w in NEG_WORDS if w in low), None)
            definition = NEG_DEFS.get(term or "", "")
            data_attr = f' data-def="{_escape_attr(definition)}"' if definition else ""
            return f'<strong class="negative"{data_attr}>{_html.escape(txt)}</strong>'
        return f'<strong class="positive">{_html.escape(txt)}</strong>'
    return re.sub(r"\*\*(.*?)\*\*", classify, htmlish)

# Unified text pipeline
def _pipe_text_plain_to_html(text_only: str, lay_gloss: Glossary | None) -> str:
    t = text_only
    t = _simplify(t, lay_gloss)
    t = _simplify_language(t)
    t = _numbers_simple(t)
    t = _grammar_cleanup(t)
    t = _annotate_terms_onepass(t)
    t = _mark_highlights(t)
    t = _convert_highlights(t)
    t = _link_organs_safe(t)
    return t

NOISE_SENT_PATTERNS = [
    r"\baxial\b",
    r"\bNECT\b",
    r"\bCECT\b",
    r"\bbrain window\b",
    r"\bimages?\s+are\s+viewed",
    r"\binterhemispheric\s+fissure\s+is\s+centered",
    r"\bappear\s+normal\b",
    r"\bare\s+normal\b",
    r"\blooks?\s+normal\b",
    r"\bno\s+abnormalit(y|ies)\b",
    r"\bnormally\s+developed\b",
    r"pneumatiz",
    r"\bparanasal\s+sinuses.*(clear|pneumatiz)",
    r"\bvisuali[sz]ed\s+lower\s+thorax\s+is\s+normal",
]
NOISE_RX = re.compile("|".join(f"(?:{p})" for p in NOISE_SENT_PATTERNS), flags=re.I)

def _prune_findings_for_public(text: str) -> str:
    if not text:
        return ""
    kept: List[str] = []
    for sent in _split_sentences(text):
        s = sent.strip()
        if not s or NOISE_RX.search(s):
            continue
        low = s.lower()
        has_number = bool(re.search(r"\b\d+(\.\d+)?\s*(mm|cm)\b", low))
        is_key = any(w in low for w in NEG_WORDS + ["stone","mass","fracture","hernia","herniation"])
        is_pos_blanket = bool(re.match(r"(?i)^(the\s+rest|other\s+areas)\b", s))
        if is_key or has_number:
            kept.append(s)
        elif is_pos_blanket:
            kept.append(s)
    # limit to essentials
    return " ".join(kept[:5])

def _extract_history(cleaned: str) -> Tuple[str, str]:
    """Return (history_text, text_without_history)."""
    hx_rx = re.compile(r"(?im)\b(clinical\s*(hx|history))\s*:\s*([^.]+)\.?", re.I)
    out = []
    text_wo = cleaned
    for m in hx_rx.finditer(cleaned):
        out.append(m.group(3).strip())
    text_wo = hx_rx.sub("", cleaned)
    return ("; ".join(dict.fromkeys(out)).strip(), text_wo)

def _normalize_common_diagnoses(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"(?i)\baging\s+brain\s+atrophy\b", "age-related **brain shrinkage**", s)
    s = re.sub(r"(?i)\bbrain\s+atrophy\b", "**brain shrinkage**", s)
    s = re.sub(r"(?i)\batrophy\b", "**brain shrinkage**", s)
    return s

# ---------- renderers -------------------------------------------------
def _render_text_long(raw: str, lay_gloss: Glossary | None) -> str:
    if not raw:
        return ""
    raw = _strip_signatures(raw)
    raw = _unwrap_soft_breaks(raw)
    paras = [p.strip() for p in re.split(r"\n{2,}", raw) if p.strip()]
    blocks = [f"<p>{_pipe_text_plain_to_html(p, lay_gloss)}</p>" for p in paras]
    return "".join(blocks)

def _render_text_bullets(raw: str, max_items: int = 8, keep_pos: int = 1) -> str:
    sentences = _split_sentences(raw)
    neg_list: List[str] = []
    pos_list: List[str] = []
    for sent in sentences:
        t = sent.strip()
        if not t:
            continue
        if re.match(r"(?i)^(conclusion|impression|ddx)[:\s]", t) or re.match(r"(?i)^dr\b", t):
            continue
        t = _numbers_simple(_grammar_cleanup(t))
        t = _annotate_terms_onepass(t)
        low = re.sub(r"<[^>]+>", "", t).lower()
        if _is_negative(low):
            neg_list.append(t)
        elif _is_positive(low):
            pos_list.append(t)

    seen = set()
    neg_list = [x for x in neg_list if not (x in seen or seen.add(x))]
    pos_list = [x for x in pos_list if not (x in seen or seen.add(x))]

    items: List[str] = []
    for t in neg_list[: max_items - 1]:
        t2 = _convert_highlights(_mark_highlights(t))
        t2 = _link_organs_safe(t2)
        items.append(f"<li>{t2}</li>")

    if keep_pos > 0:
        items.append(f"<li>{_convert_highlights('Most other areas **look normal**.')}</li>")

    if not items:
        items = [f"<li>{_convert_highlights(_mark_highlights('No major problems were seen.'))}</li>"]

    return "<ul>" + "".join(items[:max_items]) + "</ul>"

# ---------- section helpers ------------------------------------------
def _strip_labels(s: str) -> str:
    if not s:
        return ""
    s = re.sub(r"(?im)^\s*(reason|indication|procedure|technique|findings?|impression|conclusion|ddx)\s*:\s*", "", s)
    s = re.sub(r"(?i)\b(findings?|impression|conclusion|ddx)\s*:\s*", "", s)
    return s.strip()

def _infer_modality_and_region(text: str) -> str:
    low = (text or "").lower()
    modality = None
    region = None
    with_contrast = "contrast" in low

    if "mri" in low:
        modality = "MRI"
    elif re.search(r"\bct\b", low):
        modality = "CT"
    elif "ultrasound" in low or "sonograph" in low:
        modality = "Ultrasound"
    elif re.search(r"x-?ray|radiograph", low):
        modality = "X-ray"

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
            return f"{modality} of the {region}."
        if modality == "CT":
            return "CT scan" + (" with contrast." if with_contrast else ".")
        return f"{modality}."
    return ""

def _infer_reason(text: str, seed: str) -> str:
    src = seed or ""
    if not src:
        m = re.search(r"(?im)^\s*(indication|reason|history)\s*:\s*(.+)$", text or "")
        if m:
            src = m.group(2).strip()
    s = _numbers_simple(_simplify(src, None))
    s = re.sub(r"\b\?\s*", "possible ", s)
    want_lymph = bool(re.search(r"\blymphoma\b", s, flags=re.I))
    want_mass = bool(re.search(r"\bmass\b|\badenopathy\b", s, flags=re.I))
    parts: List[str] = []
    if want_mass:
        parts.append("The scan was done to check for a **mass** and **adenopathy**.")
    else:
        parts.append("The scan was done to look for a problem in the neck or head.")
    if want_lymph:
        parts.append("Doctors wanted to see if there were signs of **lymphoma**.")
    else:
        parts.append("The goal was to find a simple cause for the symptoms.")
    return " ".join(parts)

def _sanitize_concern(raw: str, source_text: str) -> str:
    if not raw:
        return ""
    has_neg = re.search(r"\b(" + "|".join(map(re.escape, NEG_WORDS)) + r")\b", source_text or "", flags=re.I)
    if not has_neg:
        return ""
    clean = re.sub(r"[^\w\s.,;:()\-'/]", "", raw)
    return clean.strip()

# ---------- main API --------------------------------------------------
def build_structured(
    text: str,
    lay_gloss: Glossary | None = None,
    language: str = "English",
    render_style: str = "bullets",   # default to simpler bullets
) -> Dict[str, str]:
    meta = parse_metadata(text or "")
    cleaned = _preclean_report(text or "")

    # pull Clinical History out of findings into reason
    hx, cleaned_wo_hx = _extract_history(cleaned)
    cleaned = cleaned_wo_hx

    secs = sections_from_text(cleaned)

    reason = secs.get("reason") or "Not provided."
    if hx:
        reason = (reason.rstrip(".") + f". History: {hx}.").strip()
    technique = secs.get("technique") or "Not provided."
    findings_src = _strip_signatures(secs.get("findings") or (cleaned or "Not described."))
    impression_src = _strip_signatures(secs.get("impression") or "")

    m = re.search(r"(?mi)^\s*comparison\s*:\s*(.+)$", cleaned)
    comparison = (m.group(1).strip() if m else "")
    m = re.search(r"(?mi)^\s*oral\s+contrast\s*:\s*(.+)$", cleaned)
    oral_contrast = (m.group(1).strip() if m else "")

    fallback_findings = _simplify(findings_src, lay_gloss)
    base_conc = impression_src or ""
    if not base_conc:
        picks: List[str] = []
        for kw in ["mass", "obstruction", "compression", "dilation", "fracture", "bleed", "appendicitis", "adenopathy", "necrotic", "atrophy"]:
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

    llm = _summarize_with_openai(cleaned, language)
    if llm:
        llm_reason = _strip_labels(llm.get("reason", ""))
        llm_tech = _strip_labels(llm.get("technique", ""))
        inferred_reason = _infer_reason(cleaned, llm_reason or reason)
        inferred_tech = _infer_modality_and_region(cleaned)
        reason = inferred_reason or llm_reason or reason
        technique = inferred_tech or llm_tech or technique

        raw_findings = (llm.get("findings", "") or "").strip() or fallback_findings
        raw_conclusion = (llm.get("conclusion", "") or "").strip() or fallback_conclusion
        concern = (llm.get("concern", "") or "").strip() or concern
    else:
        reason = _infer_reason(cleaned, reason)
        technique = _infer_modality_and_region(cleaned) or technique
        raw_findings = fallback_findings
        raw_conclusion = fallback_conclusion

    concern = _sanitize_concern(concern, cleaned)

    # simplify findings/conclusion text before rendering
    raw_findings = _rewrite_simple_terms(_normalize_common_diagnoses(_strip_labels(_prune_findings_for_public(_strip_labels(raw_findings)))))
    raw_conclusion = _rewrite_simple_terms(_normalize_common_diagnoses(_strip_labels(raw_conclusion)))
    raw_findings = _enforce_simple_bullets(raw_findings)
    raw_conclusion = _enforce_simple_bullets(raw_conclusion, max_words=10)

    # render: always prefer bullets for public simplicity
    findings = _render_text_bullets(raw_findings, max_items=5, keep_pos=1)
    conclusion = _render_text_bullets(raw_conclusion, max_items=2, keep_pos=0)

    reason_html = _pipe_text_plain_to_html(reason, lay_gloss)
    technique_html = _pipe_text_plain_to_html(technique, lay_gloss)
    concern_html = _render_text_long(concern, lay_gloss) if concern else concern

    words = len(re.findall(r"\w+", cleaned))
    sentences = len(re.findall(r"[.!?]+", cleaned))
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
