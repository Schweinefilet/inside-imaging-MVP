# app.py
import os
import io
import re
import json
import logging
import boto3
from botocore.config import Config

_AWS_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1"

_textract_client = None
def _textract():
    global _textract_client
    if _textract_client is None:
        _textract_client = boto3.client(
            "textract",
            region_name=_AWS_REGION,
            config=Config(retries={"max_attempts": 3, "mode": "standard"})
        )
    return _textract_client


from dotenv import load_dotenv
load_dotenv(dotenv_path=".env", override=True)

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    make_response,
    jsonify,
    abort,
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from flask_cors import CORS

# local db
from src import db

# --- logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
k = os.getenv("OPENAI_API_KEY", "")
logging.info("OPENAI_API_KEY loaded=%s len=%d", "yes" if bool(k) else "no", len(k))
logging.info("INSIDEIMAGING_ALLOW_LLM=%r", os.getenv("INSIDEIMAGING_ALLOW_LLM"))
logging.info("OPENAI_MODEL=%r", os.getenv("OPENAI_MODEL"))

# --- app ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# CORS
CORS(app, resources={r"/*": {"origins": os.getenv("CORS_ORIGINS", "https://schweinefilet.github.io")}})

# available languages
LANGUAGES = ["English", "Kiswahili"]

# pricing + tokens
USD_PER_REPORT = 1.00
KES_PER_USD = 129
TOKENS_PER_REPORT = 1

# curated content for magazine + blog pages
MAGAZINE_ISSUES = [
    {
        "title": "July 2025 · THE FUTURE OF AI IN IMAGING",
        "url": "magazine/July-2025.pdf",
        "note": "Upload static/magazine/July-2025.pdf",
    },
]

BLOG_POSTS = [
    {
        "title": "The Evolution of Diagnostic Imaging: From X-Rays to AI",
        "summary": "Exploring how medical imaging has transformed over the decades and what artificial intelligence means for the future of radiology and patient care.",
        "author": "Dr. Sarah Mitchell",
        "author_bio": "Board-certified radiologist with 15 years of experience in diagnostic imaging and AI integration.",
        "author_image": None,
        "author_linkedin": "https://linkedin.com/in/placeholder",
        "author_twitter": "https://twitter.com/placeholder",
        "author_email": "editor@insideimaging.example",
        "author_website": None,
        "date": "January 2025",
        "read_time": "8 min read",
        "url": "#",
    },
    {
        "title": "Communicating Complex Findings: A Patient-Centered Approach",
        "summary": "Practical strategies for translating medical jargon into clear, compassionate explanations that empower patients to understand their imaging results.",
        "author": "Dr. James Chen",
        "author_bio": "Interventional radiologist passionate about patient education and accessible healthcare communication.",
        "author_image": None,
        "author_linkedin": "https://linkedin.com/in/placeholder",
        "author_twitter": None,
        "author_email": "editor@insideimaging.example",
        "author_website": None,
        "date": "February 2025",
        "read_time": "6 min read",
        "url": "#",
    },
    {
        "title": "The Role of AI in Early Disease Detection",
        "summary": "How machine learning algorithms are helping radiologists identify subtle abnormalities earlier, improving patient outcomes and treatment planning.",
        "author": "Dr. Priya Sharma",
        "author_bio": "Diagnostic radiologist and AI researcher focused on computer-aided detection systems.",
        "author_image": None,
        "author_linkedin": "https://linkedin.com/in/placeholder",
        "author_twitter": "https://twitter.com/placeholder",
        "author_email": "editor@insideimaging.example",
        "author_website": "https://example.com",
        "date": "March 2025",
        "read_time": "10 min read",
        "url": "#",
    },
]

MARQUEE_IMAGES = [
    # Placeholder images for pilot program
    # Real radiology examples will be added after IRB approval
    # To add your images: replace the files in static/images/marquee/
    # Recommended format: JPG or PNG, 320x300px or 400x500px, under 500KB
    "/static/images/marquee/placeholder-1.jpg",
    "/static/images/marquee/placeholder-2.jpg",
    "/static/images/marquee/placeholder-3.jpg",
    "/static/images/marquee/placeholder-4.jpg",
    "/static/images/marquee/placeholder-5.jpg",
    "/static/images/marquee/placeholder-6.jpg",
    "/static/images/marquee/placeholder-7.jpg",
    "/static/images/marquee/placeholder-8.jpg",
    "/static/images/marquee/placeholder-9.jpg",
    "/static/images/marquee/placeholder-10.jpg",
    "/static/images/marquee/placeholder-11.jpg",
    "/static/images/marquee/placeholder-12.jpg",
    "/static/images/marquee/placeholder-13.jpg",
    "/static/images/marquee/placeholder-14.jpg",
    "/static/images/marquee/placeholder-15.jpg",
    "/static/images/marquee/placeholder-16.jpg",
]

# Initialize database
try:
    db.init_db()
except Exception:
    logging.exception("Database initialization failed")

# --- translate wiring ---
try:
    from src.translate import Glossary, build_structured  # type: ignore
except Exception:
    logging.exception("translate import failed")
    Glossary = None  # type: ignore

    def build_structured(report_text: str, glossary=None, language: str = "English"):
        return {
            "reason": "",
            "technique": "",
            "findings": (report_text or "").strip(),
            "conclusion": "",
            "concern": "",
        }

# try to load a glossary if you have one; otherwise None is fine
LAY_GLOSS = None
try:
    if Glossary:
        gloss_path = os.path.join(os.path.dirname(__file__), "data", "glossary.csv")
        if os.path.exists(gloss_path):
            LAY_GLOSS = Glossary.load(gloss_path)
except Exception:
    logging.exception("glossary load failed")
    LAY_GLOSS = None

# PDF engine
try:
    from weasyprint import HTML  # type: ignore
except Exception:
    HTML = None  # type: ignore


def _extract_text_from_pdf_bytes(data: bytes) -> str:
    """Robust PDF text extraction using pdfminer.six."""
    try:
        from pdfminer.high_level import extract_text  # type: ignore
    except Exception:
        logging.exception("pdfminer.six not available")
        return ""
    try:
        return extract_text(io.BytesIO(data)) or ""
    except Exception:
        logging.exception("pdfminer extract_text failed")
        return ""


def _extract_text_from_image_bytes(data: bytes) -> str:
    """
    Extract text from an image using AWS Textract DetectDocumentText.
    Works best for phone photos (JPEG/PNG). Max 5 MB for Bytes input.
    """
    if not data:
        return ""

    # Simple guard: DetectDocumentText supports PNG/JPEG (Bytes) up to 5 MB
    if len(data) > 5 * 1024 * 1024:
        logging.warning("Image >5MB; Textract DetectDocumentText requires <=5MB for Bytes.")
        return ""

    try:
        resp = _textract().detect_document_text(Document={"Bytes": data})
    except Exception:
        logging.exception("Textract DetectDocumentText failed")
        return ""

    # Pull out LINE blocks in natural reading order
    lines = []
    for block in resp.get("Blocks", []):
        if block.get("BlockType") == "LINE" and block.get("Text"):
            lines.append(block["Text"].strip())

    # Fallback: if no LINEs, try WORDs
    if not lines:
        words = [b.get("Text", "").strip() for b in resp.get("Blocks", []) if b.get("BlockType") == "WORD"]
        lines = [" ".join(w for w in words if w)]

    text = "\n".join(l for l in lines if l)
    return text.strip()



def _pdf_response_from_html(html_str: str, *, filename="inside-imaging-report.pdf", inline: bool = False):
    if not HTML:
        raise RuntimeError("WeasyPrint is not installed or failed to import")
    # host_url lets WeasyPrint resolve /static and relative asset URLs
    pdf_bytes = HTML(string=html_str, base_url=request.host_url).write_pdf()
    resp = make_response(pdf_bytes)
    resp.headers["Content-Type"] = "application/pdf"
    disp = "inline" if inline else "attachment"
    resp.headers["Content-Disposition"] = f'{disp}; filename="{filename}"'
    return resp


def _parse_brain_lesion(structured: dict) -> dict:
    """Parse brain lesion location and size from conclusion/findings text."""
    import re
    
    conclusion = (structured.get("conclusion") or "").lower()
    findings = (structured.get("findings") or "").lower()
    # Strip HTML tags
    conclusion = re.sub(r'<[^>]+>', ' ', conclusion)
    findings = re.sub(r'<[^>]+>', ' ', findings)
    combined_text = conclusion + ' ' + findings
    
    # Location mapping: [axial_x, axial_y, sagittal_x, sagittal_y, coronal_x, coronal_y]
    location_map = {
        'right frontoparietal': [145, 95, 135, 90, 155, 85],
        'left frontoparietal': [95, 95, 135, 90, 85, 85],
        'right frontal': [140, 85, 125, 75, 150, 75],
        'left frontal': [100, 85, 125, 75, 90, 75],
        'right parietal': [150, 100, 140, 95, 160, 90],
        'left parietal': [90, 100, 140, 95, 80, 90],
        'right temporal': [155, 115, 145, 110, 165, 105],
        'left temporal': [85, 115, 145, 110, 75, 105],
        'right occipital': [155, 125, 155, 130, 165, 120],
        'left occipital': [85, 125, 155, 130, 75, 120],
        'sphenoid wing': [130, 105, 120, 100, 135, 100],
        'greater sphenoid wing': [135, 105, 120, 100, 140, 100],
        'cerebellum': [120, 145, 80, 165, 120, 165],
        'brainstem': [120, 155, 90, 175, 120, 175],
        'thalamus': [120, 110, 115, 110, 120, 110],
        'basal ganglia': [115, 110, 115, 105, 115, 105]
    }
    
    # Parse size (e.g., "5.4 x 5.6 x 6.7 cm" or "measures 2.5 cm")
    size_match = re.search(r'(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*cm|measures?\s+(\d+\.?\d*)\s*cm', combined_text, re.IGNORECASE)
    avg_size = 18  # default radius
    if size_match:
        if size_match.group(1):
            dims = [float(size_match.group(1)), float(size_match.group(2)), float(size_match.group(3))]
            avg_size = min(30, max(10, sum(dims) / 3 * 3))  # scale to pixels
        elif size_match.group(4):
            avg_size = min(30, max(10, float(size_match.group(4)) * 3))
    
    # Find best location match
    best_match = None
    best_length = 0
    for loc in location_map:
        if loc in combined_text and len(loc) > best_length:
            best_match = loc
            best_length = len(loc)
    
    default_coords = [145, 95, 135, 90, 155, 85]
    return {
        'location': best_match or 'right frontoparietal',
        'coords': location_map.get(best_match) if best_match else default_coords,
        'size': int(avg_size),
        'found': best_match is not None
    }


_TRIAGE_SECTION_RX = re.compile(
    r"(?im)^\s*(findings|impression|conclusion|technique|history|clinical\s+history|"
    r"indication|comparison|procedure|exam(?:ination)?|study|details)\s*[:\-]"
)
_TRIAGE_MODALITY_TOKENS = [
    "ct", "mri", "x-ray", "xray", "ultrasound", "pet", "spect", "angiogram",
    "fluoroscopy", "mammo", "mammogram", "cect", "mra", "cta", "doppler",
]
_TRIAGE_IMAGING_TERMS = [
    "lesion", "mass", "nodule", "enhancement", "attenuation", "hyperdense",
    "hypodense", "hyperintense", "hypointense", "density", "signal", "axial",
    "sagittal", "coronal", "sequence", "cm", "mm", "vertebra", "lobar",
    "hepatic", "renal", "ventricle", "parenchyma", "impression", "findings",
    "technique", "study", "comparison", "contrast",
]
_TRIAGE_NEGATIVE_TOKENS = [
    "syllabus", "semester", "homework", "assignment", "professor", "student",
    "lecture", "quiz", "final exam", "midterm", "credit hours", "office hours",
    "course objectives", "course description", "grading policy", "title ix",
    "canvas site", "attendance policy",
]


def _triage_radiology_report(text: str) -> tuple[bool, dict]:
    """Quick heuristic to reject non-radiology uploads before hitting the LLM."""

    sample = (text or "").strip()
    if not sample:
        return False, {"reason": "empty"}

    snippet = sample[:20000]
    lower = snippet.lower()

    # Basic counts
    words = re.findall(r"\b\w+\b", snippet)
    word_count = len(words)
    section_hits = {match.group(1).lower() for match in _TRIAGE_SECTION_RX.finditer(snippet)}
    modality_hits = [token for token in _TRIAGE_MODALITY_TOKENS if token in lower]
    imaging_hits = [token for token in _TRIAGE_IMAGING_TERMS if token in lower]
    measurement_count = len(re.findall(r"\b\d+(?:\.\d+)?\s*(?:mm|cm)\b", lower))
    negative_hits = [token for token in _TRIAGE_NEGATIVE_TOKENS if token in lower]

    # Legacy keyword heuristics to preserve prior thresholds
    radiology_keywords = [
        "radiology", "radiologist", "imaging", "scan", "ct", "mri", "x-ray", "xray",
        "ultrasound", "pet", "findings", "impression", "technique", "contrast",
        "examination", "study", "patient", "indication", "conclusion", "comparison",
    ]
    anatomy_terms = [
        "brain", "lung", "liver", "kidney", "heart", "spine", "abdomen", "pelvis",
        "chest", "thorax", "head", "skull", "bone", "soft tissue", "vessel", "artery",
        "vein", "organ", "lesion", "mass", "nodule",
    ]
    radiology_keyword_count = sum(1 for keyword in radiology_keywords if keyword in lower)
    anatomy_count = sum(1 for term in anatomy_terms if term in lower)

    score = 0
    if word_count >= 90:
        score += 1
    if len(section_hits) >= 2:
        score += 2
    elif len(section_hits) == 1:
        score += 1
    if radiology_keyword_count >= 3:
        score += 1
    if anatomy_count >= 2 or len(imaging_hits) >= 4:
        score += 1
    if modality_hits:
        score += 2
    if measurement_count >= 3:
        score += 2
    elif measurement_count >= 1:
        score += 1
    if "impression" in section_hits:
        score += 1
    if "findings" in section_hits:
        score += 1

    diagnostics = {
        "word_count": word_count,
        "sections": sorted(section_hits),
        "modalities": modality_hits,
        "imaging_hits": imaging_hits[:10],
        "radiology_keyword_count": radiology_keyword_count,
        "anatomy_count": anatomy_count,
        "measurement_count": measurement_count,
        "negative_hits": negative_hits,
        "score": score,
    }

    # Hard rejection conditions
    if word_count < 80 and not (len(section_hits) >= 3 and modality_hits):
        diagnostics["reason"] = "too_short"
        return False, diagnostics
    if negative_hits and score < 6:
        diagnostics["reason"] = "non_medical_tokens"
        return False, diagnostics
    if not modality_hits and len(section_hits) < 2 and len(imaging_hits) < 5:
        diagnostics["reason"] = "insufficient_radiology_markers"
        return False, diagnostics
    if score < 5:
        diagnostics["reason"] = "low_confidence"
        return False, diagnostics

    diagnostics["reason"] = "ok"
    return True, diagnostics


def _extract_focus_details(raw_text: str, organ: str | None) -> dict:
    if not organ:
        return {}

    low = (raw_text or "").lower()
    focus: dict = {"organ": organ}

    if organ == 'lung':
        has_right = bool(re.search(r'\bright[^.,;]{0,40}(lung|lobe)', low))
        has_left = bool(re.search(r'\bleft[^.,;]{0,40}(lung|lobe)', low))
        has_bilateral = bool(re.search(r'\bbilateral\b|\bboth\s+lungs?\b|\ball\s+lobes\b', low))
        if has_bilateral or (has_right and has_left):
            focus['laterality'] = 'bilateral'
        elif has_right:
            focus['laterality'] = 'right'
        elif has_left:
            focus['laterality'] = 'left'

        if re.search(r'\b(apex|apical|upper\s+lobe|upper\s+zone|superior\s+segment)\b', low):
            focus['zone'] = 'upper'
        elif re.search(r'\bmiddle\s+lobe\b|\bmid\s+lobe\b|\bperihilar\b', low):
            focus['zone'] = 'middle'
        elif re.search(r'\b(lower\s+lobe|lower\s+zone|basal|base|inferior\s+segment)\b', low):
            focus['zone'] = 'lower'

    elif organ == 'kidney':
        has_right = bool(re.search(r'\bright[^.,;]{0,30}(kidney|renal)', low))
        has_left = bool(re.search(r'\bleft[^.,;]{0,30}(kidney|renal)', low))
        has_bilateral = bool(re.search(r'\bbilateral\b|\bboth\s+kidneys\b|\ball\s+renal\b', low))
        if has_bilateral or (has_right and has_left):
            focus['laterality'] = 'bilateral'
        elif has_right:
            focus['laterality'] = 'right'
        elif has_left:
            focus['laterality'] = 'left'

        if re.search(r'\bupper\s+pole\b|\bsuperior\s+pole\b', low):
            focus['zone'] = 'upper'
        elif re.search(r'\blower\s+pole\b|\binferior\s+pole\b', low):
            focus['zone'] = 'lower'
        elif re.search(r'\bmid(?:dle)?\s+pole\b|\binterpolar\b', low):
            focus['zone'] = 'mid'

    elif organ == 'liver':
        has_right = bool(re.search(r'\bright\s+(hepatic\s+)?lobe\b', low))
        has_left = bool(re.search(r'\bleft\s+(hepatic\s+)?lobe\b', low))
        has_bilateral = bool(re.search(r'\bboth\s+lobe\b|\bdiffuse\b|\bbilateral\b', low))
        if has_bilateral or (has_right and has_left):
            focus['laterality'] = 'bilateral'
        elif has_right:
            focus['laterality'] = 'right'
        elif has_left:
            focus['laterality'] = 'left'

        segment_hits = re.findall(r'\bsegment\s+([ivx]{1,4})\b', low)
        if segment_hits:
            segment_map = {
                'i': 'caudate',
                'ii': 'left', 'iii': 'left', 'iv': 'left', 'iva': 'left', 'ivb': 'left',
                'v': 'right', 'vi': 'right', 'vii': 'right', 'viii': 'right'
            }
            first = segment_hits[0]
            focus['segment'] = first.upper()
            zone = segment_map.get(first.lower())
            if zone:
                focus['segment_group'] = zone
                if zone in ('left', 'right') and 'laterality' not in focus:
                    focus['laterality'] = zone

    elif organ == 'spine':
        levels: set[str] = set()
        for token in re.findall(r'\b[cClLtTsS][0-9]{1,2}\b', low):
            levels.add(token.upper())
        for start, end in re.findall(r'\b([cClLtTsS][0-9]{1,2})\s*[-–to]+\s*([cClLtTsS]?[0-9]{1,2})\b', low):
            levels.add(start.upper())
            if end:
                prefix = end[0] if end and end[0].isalpha() else start[0]
                digits = end[1:] if end and end[0].isalpha() else end
                levels.add((prefix + digits).upper())
        if levels:
            order_map = {'C': 0, 'T': 1, 'L': 2, 'S': 3}
            focus['levels'] = sorted(levels, key=lambda lvl: (order_map.get(lvl[0], 4), int(re.sub(r'[^0-9]', '', lvl) or 0)))
            if any(lvl.startswith('L') for lvl in levels):
                focus['region'] = 'lumbar'
            elif any(lvl.startswith('T') for lvl in levels):
                focus['region'] = 'thoracic'
            elif any(lvl.startswith('C') for lvl in levels):
                focus['region'] = 'cervical'
            elif any(lvl.startswith('S') for lvl in levels):
                focus['region'] = 'sacral'

    elif organ == 'brain':
        if re.search(r'\bright[^.]{0,40}(frontal|parietal|temporal|occipital|hemisphere)', low):
            focus['laterality'] = 'right'
        elif re.search(r'\bleft[^.]{0,40}(frontal|parietal|temporal|occipital|hemisphere)', low):
            focus['laterality'] = 'left'

        for region_key, label in [
            ('frontal', 'frontal'),
            ('parietal', 'parietal'),
            ('temporal', 'temporal'),
            ('occipital', 'occipital'),
            ('cerebell', 'cerebellum'),
            ('brainstem', 'brainstem')
        ]:
            if region_key in low:
                focus.setdefault('regions', []).append(label)

        if 'regions' in focus:
            focus['regions'] = list(dict.fromkeys(focus['regions']))

    if len(focus) <= 1:
        return {}
    return focus


def _detect_abnormality_and_organ(structured: dict, patient: dict) -> dict:
    """
    Detect if report shows abnormalities and identify the affected organ.
    Returns: {'has_abnormality': bool, 'organ': str, 'abnormality_type': str}
    """
    import re
    
    conclusion = (structured.get("conclusion") or "").lower()
    findings = (structured.get("findings") or "").lower()
    study = (patient.get("study") or "").lower()
    
    # Strip HTML tags
    conclusion = re.sub(r'<[^>]+>', ' ', conclusion)
    findings = re.sub(r'<[^>]+>', ' ', findings)
    combined = conclusion + ' ' + findings + ' ' + study
    
    # Normal scan indicators
    normal_indicators = [
        r'\bnormal\b', r'\bunremarkable\b', r'\bno\s+abnormalit', r'\bwithin\s+normal\s+limits\b',
        r'\bno\s+significant\b', r'\bno\s+acute\b', r'\bclear\b.*\blungs?\b', r'\bintact\b'
    ]
    
    # Abnormality indicators
    abnormal_indicators = [
        r'\bmass\b', r'\btumou?r\b', r'\blesion\b', r'\bmeningioma\b', r'\bcancer\b',
        r'\bfracture\b', r'\bbleed\b', r'\bhemorrhage\b', r'\binfarct\b', r'\bstroke\b',
        r'\bedema\b', r'\bswelling\b', r'\bobstruction\b', r'\benlarged\b',
        r'\badenopathy\b', r'\bnodule\b', r'\bhydro\w+\b', r'\bherniation\b',
        r'\bshift\b', r'\bcompression\b', r'\beffusion\b', r'\bpneumonia\b'
    ]
    
    # Count indicators
    normal_count = sum(1 for pattern in normal_indicators if re.search(pattern, combined, re.I))
    abnormal_count = sum(1 for pattern in abnormal_indicators if re.search(pattern, combined, re.I))
    
    has_abnormality = abnormal_count > 0 and abnormal_count >= normal_count
    
    # Organ detection (order matters - more specific first)
    organ = None
    # Brain/head - but NOT "head of pancreas" or other anatomical heads
    if re.search(r'\b(brain|skull|cerebral|intracranial|cranial)\b', combined, re.I):
        organ = 'brain'
    elif re.search(r'\bhead\b', combined, re.I) and not re.search(r'\bhead\s+of\s+(pancreas|femur)\b', combined, re.I):
        organ = 'brain'
    elif re.search(r'\b(lung|pulmonary|chest|thorax|bronch)\b', combined, re.I):
        organ = 'lung'
    elif re.search(r'\b(liver|hepatic)\b', combined, re.I):
        organ = 'liver'
    elif re.search(r'\b(kidney|renal)\b', combined, re.I):
        organ = 'kidney'
    elif re.search(r'\b(spine|spinal|cervical|lumbar|thoracic|vertebra)\b', combined, re.I):
        organ = 'spine'
    elif re.search(r'\b(abdomen|abdominal|belly|pancreas|pancreatic)\b', combined, re.I):
        organ = 'abdomen'
    elif re.search(r'\b(pelvis|pelvic)\b', combined, re.I):
        organ = 'pelvis'
    
    # Abnormality type
    abnormality_type = None
    if has_abnormality:
        if re.search(r'\bmass\b|\btumou?r\b|\blesion\b|\bmeningioma\b|\bcancer\b', combined, re.I):
            abnormality_type = 'mass'
        elif re.search(r'\bfracture\b', combined, re.I):
            abnormality_type = 'fracture'
        elif re.search(r'\bbleed\b|\bhemorrhage\b', combined, re.I):
            abnormality_type = 'bleed'
        elif re.search(r'\bedema\b|\bswelling\b', combined, re.I):
            abnormality_type = 'edema'
        elif re.search(r'\binfection\b|\bpneumonia\b', combined, re.I):
            abnormality_type = 'infection'
        else:
            abnormality_type = 'other'
    
    focus = _extract_focus_details(combined, organ) if organ else {}

    return {
        'has_abnormality': has_abnormality,
        'organ': organ,
        'abnormality_type': abnormality_type,
        'focus': focus
    }


@app.route("/dashboard", methods=["GET"])
def dashboard():
    stats = db.get_stats()
    recent_reports = session.get("recent_reports", [])
    
    # Get user's persistent reports if logged in
    username = session.get("username")
    user_reports = []
    if username:
        try:
            user_reports = db.get_user_reports(username, limit=5)
        except Exception:
            logging.exception("Failed to fetch user reports")
    
    return render_template("index.html", stats=stats, languages=LANGUAGES, 
                          recent_reports=recent_reports, user_reports=user_reports)


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return redirect(url_for("dashboard"))

    file = request.files.get("file")
    lang = request.form.get("language", "English")
    file_text = request.form.get("file_text", "")
    extracted = ""
    src_kind = ""

    # Prefer pasted text if provided
    if file_text and file_text.strip():
        extracted = file_text.strip()
        src_kind = "text"
    elif file and file.filename:
        fname = secure_filename(file.filename)
        data = file.read()
        lower_name = fname.lower()
        try:
            if lower_name.endswith(".pdf"):
                extracted = _extract_text_from_pdf_bytes(data)
                src_kind = "pdf"
            elif lower_name.endswith((".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp")):
                extracted = _extract_text_from_image_bytes(data)
                src_kind = "image"
                if not extracted:
                    flash(
                        "Unable to extract text from the image. The image may be too large (>5MB), "
                        "corrupted, or contain no readable text. Please try a clearer image or paste the text directly.",
                        "error",
                    )
                    return redirect(url_for("dashboard"))  # ✅ Fixed
            else:
                try:
                    extracted = data.decode("utf-8", "ignore")
                    src_kind = "text"
                except Exception:
                    logging.exception("decode failed; extracted empty")
        except Exception:
            logging.exception("file handling failed; extracted empty")

    logging.info("len(extracted)=%s kind=%s", len(extracted or ""), src_kind or "?")

    triage_ok, triage_diag = _triage_radiology_report(extracted)
    if not triage_ok:
        message = (
            "The uploaded file doesn't appear to be a radiology report. "
            "Please upload a full imaging report (with sections like Findings and Impression)."
        )
        flash(message, "error")
        logging.warning("Upload triage rejected: %s", triage_diag)
        return redirect(url_for("dashboard"))

    # Build structured summary
    try:
        logging.info("calling build_structured language=%s", lang)
        S = build_structured(extracted, LAY_GLOSS, language=lang) or {}
        logging.info(
            "summary_keys=%s",
            {k: len((S or {}).get(k) or "") for k in ("reason", "technique", "findings", "conclusion", "concern")},
        )
    except Exception:
        logging.exception("build_structured failed")
        S = {"reason": "", "technique": "", "findings": "", "conclusion": "", "concern": ""}

    # Patient and study from structured metadata
    patient_struct = S.get("patient") if isinstance(S, dict) else None
    if isinstance(patient_struct, dict) and patient_struct:
        patient = {
            "hospital": patient_struct.get("hospital", ""),
            "study": patient_struct.get("study", "Unknown"),
            "name": patient_struct.get("name", ""),
            "sex": patient_struct.get("sex", ""),
            "age": patient_struct.get("age", ""),
            "date": patient_struct.get("date", ""),
            "history": patient_struct.get("history", ""),
        }
    else:
        patient = {
            "hospital": S.get("hospital", ""),
            "study": S.get("study", "Unknown"),
            "name": S.get("name", ""),
            "sex": S.get("sex", ""),
            "age": S.get("age", ""),
            "date": S.get("date", ""),
            "history": "",
        }
    study = {"organ": patient.get("study") or "Unknown"}
    structured = S

    # Simple report stats for UI
    high_html = (S.get("findings", "") or "") + (S.get("conclusion", "") or "")
    report_stats = {
        "words": len((extracted or "").split()),
        "sentences": len(re.findall(r"[.!?]+", extracted or "")),
        "highlights_positive": high_html.count('class="ii-pos"'),
        "highlights_negative": high_html.count('class="ii-neg"'),
    }

    # Detect abnormality and organ for smart visualization
    diagnosis = _detect_abnormality_and_organ(structured, patient)

    # persist for later pages like /payment and PDF download
    session["structured"] = structured
    session["patient"] = patient
    session["language"] = lang
    session["diagnosis"] = diagnosis

    report_id = None
    try:
        username = session.get("username", "")
        report_id = db.store_report_event(patient, structured, report_stats, lang, username)
    except Exception:
        logging.exception("Failed to persist report analytics.")

    if report_id:
        try:
            brief = db.get_report_brief(report_id)
        except Exception:
            logging.exception("Failed to fetch report brief.")
            brief = None
        if brief:
            history = session.get("recent_reports") or []
            filtered = [item for item in history if item.get("id") != report_id]
            session["recent_reports"] = [brief] + filtered[:4]

    return render_template(
        "result.html",
        S=structured,
        structured=structured,
        patient=patient,
        extracted=extracted,
        study=study,
        language=lang,
        report_stats=report_stats,
        diagnosis=diagnosis,
    )


@app.route("/reports/<int:report_id>")
def report_detail(report_id: int):
    record = db.get_report_detail(report_id)
    if not record:
        abort(404)

    structured = dict(record.get("structured") or {})
    patient = dict(record.get("patient") or {})
    language = record.get("language") or "English"

    findings_blob = (structured.get("findings") or "") + (structured.get("conclusion") or "")
    highlight_pos = findings_blob.count('class="ii-pos"')
    highlight_neg = findings_blob.count('class="ii-neg"')

    structured.setdefault("word_count", record.get("word_count", 0))
    structured.setdefault("sentence_count", 0)
    structured.setdefault("highlights_positive", highlight_pos)
    structured.setdefault("highlights_negative", highlight_neg)

    report_stats = {
        "words": structured.get("word_count", 0),
        "sentences": structured.get("sentence_count", 0),
        "highlights_positive": highlight_pos,
        "highlights_negative": highlight_neg,
    }

    session["structured"] = structured
    session["patient"] = patient
    session["language"] = language

    study = {"organ": patient.get("study") or "Unknown"}
    diagnosis = _detect_abnormality_and_organ(structured, patient)
    session["diagnosis"] = diagnosis

    return render_template(
        "result.html",
        S=structured,
        structured=structured,
        patient=patient,
        extracted="",
        study=study,
        language=language,
        report_stats=report_stats,
        diagnosis=diagnosis,
    )


@app.route("/download-pdf", methods=["GET", "POST"])
def download_pdf():
    try:
        if request.method == "POST":
            structured_raw = request.form.get("structured")
            patient_raw = request.form.get("patient")
            structured = json.loads(structured_raw) if structured_raw else session.get("structured", {}) or {}
            patient = json.loads(patient_raw) if patient_raw else session.get("patient", {}) or {}
        else:
            structured = session.get("structured", {}) or {}
            patient = session.get("patient", {}) or {}
    except Exception as e:
        logging.exception("Failed to parse form JSON")
        return jsonify({"error": "bad form JSON", "detail": str(e)}), 400

    # Detect abnormality and organ for conditional visualization
    diagnosis = _detect_abnormality_and_organ(structured, patient)
    
    # Parse brain lesion data for dynamic positioning (only if brain abnormality)
    lesion_data = None
    if diagnosis['has_abnormality'] and diagnosis['organ'] == 'brain':
        lesion_data = _parse_brain_lesion(structured)
    
    html_str = render_template("pdf_report.html", structured=structured, patient=patient, lesion_data=lesion_data, diagnosis=diagnosis)

    # hard fail if PDF fails. no HTML fallback.
    try:
        return _pdf_response_from_html(html_str, filename="inside-imaging-report.pdf", inline=False)
    except Exception as e:
        logging.exception("WeasyPrint PDF render failed")
        return jsonify({"error": "pdf_failed", "detail": str(e)}), 500


@app.get("/pdf-smoke")
def pdf_smoke():
    test_html = """
    <!doctype html><meta charset="utf-8">
    <style>@page{size:A4;margin:20mm} body{font-family:Arial}</style>
    <h1>WeasyPrint OK</h1><p>Static image test below.</p>
    <img src="/static/logo.png" alt="logo" height="24">
    """
    try:
        return _pdf_response_from_html(test_html, filename="smoke.pdf", inline=True)
    except Exception as e:
        logging.exception("Smoke failed")
        return jsonify({"error": "smoke_failed", "detail": str(e)}), 500


@app.get("/report/preview")
def report_preview():
    """Quick HTML preview of the PDF template with session data."""
    structured = session.get("structured", {}) or {}
    patient = session.get("patient", {}) or {}
    return render_template("pdf_report.html", structured=structured, patient=patient)


@app.route("/", methods=["GET"])
@app.route("/projects")
def projects():
    stats = db.get_stats()
    return render_template(
        "projects.html",
        posts=BLOG_POSTS,
        marquee_images=MARQUEE_IMAGES,
        submit_url="mailto:editor@insideimaging.example?subject=Radiologist%20Blog%20Pitch",
        stats=stats,
        languages=LANGUAGES,
    )


@app.route("/magazine")
def magazine():
    archive = []
    magazine_url = None

    for item in MAGAZINE_ISSUES:
        record = dict(item)
        raw_url = record.get("url")
        resolved_url = None
        if raw_url:
            if raw_url.startswith(("http://", "https://", "/")):
                resolved_url = raw_url
            else:
                resolved_url = url_for("static", filename=raw_url.lstrip("/"))
            record["url"] = resolved_url
            if magazine_url is None:
                magazine_url = resolved_url
        archive.append(record)

    return render_template("language.html", magazine_url=magazine_url, archive=archive)


@app.route("/language")
def legacy_language():
    return redirect(url_for("magazine"))


@app.route("/blogs")
def blogs():
    return redirect(url_for("projects", _anchor="insights"))


@app.route("/report_status")
def report_status():
    stats = db.get_stats()
    
    # Prepare JSON-safe data for JavaScript
    stats_json = {
        "reportsTimeSeries": stats.get("time_series", []),
        "ageData": [{"label": label, "value": count} for label, count in stats.get("age_ranges", {}).items()],
        "genderData": [
            {"label": "Female", "value": stats.get("gender", {}).get("female", 0)},
            {"label": "Male", "value": stats.get("gender", {}).get("male", 0)},
            {"label": "Other", "value": stats.get("gender", {}).get("other", 0)}
        ],
        "languagesData": stats.get("languages", []),
        "modalitiesData": stats.get("studies", []),
        "findingsData": [{"label": entry["label"].capitalize(), "value": entry["count"]} for entry in stats.get("diseases", [])]
    }
    
    return render_template("report_status.html", stats=stats, stats_json=stats_json)


@app.route("/payment")
def payment():
    # supply context expected by template
    structured_session = session.get("structured")
    if isinstance(structured_session, dict):
        structured = dict(structured_session)
    else:
        structured = {}

    structured.setdefault("report_type", "CT Scan")
    structured["price"] = f"{USD_PER_REPORT:.2f}"
    session["structured"] = structured

    kes_amount = USD_PER_REPORT * KES_PER_USD
    kes_display = f"{kes_amount:,.2f}".rstrip("0").rstrip(".")
    pricing = {
        "usd": USD_PER_REPORT,
        "usd_display": f"{USD_PER_REPORT:.2f}",
        "kes": kes_amount,
        "kes_display": kes_display,
        "tokens": TOKENS_PER_REPORT,
        "exchange_rate": KES_PER_USD,
    }
    lang = session.get("language", "English")
    return render_template("payment.html", structured=structured, language=lang, pricing=pricing)


@app.route("/help")
def help_page():
    return render_template("help.html")


@app.route("/team")
def team():
    """Team page with member bios and photos"""
    return render_template("team.html")


@app.route("/profile")
def profile():
    username = session.get("username")
    if not username:
        return redirect(url_for("login"))
    
    # Get user's feedback submissions
    user_feedback = db.get_user_feedback(username)
    
    # Check if user is admin (for now, hardcoded check - you can enhance this)
    is_admin = username in ["admin", "radiologist"]
    
    return render_template("profile.html", feedback_list=user_feedback, is_admin=is_admin)


@app.route("/submit-feedback", methods=["POST"])
def submit_feedback():
    """Handle feedback submission from radiologists/users"""
    username = session.get("username")
    if not username:
        flash("Please log in to submit feedback.", "error")
        return redirect(url_for("login"))
    
    try:
        feedback_type = request.form.get("feedback_type", "").strip()
        subject = request.form.get("subject", "").strip()
        original_text = request.form.get("original_text", "").strip()
        corrected_text = request.form.get("corrected_text", "").strip()
        description = request.form.get("description", "").strip()
        
        if not feedback_type or not subject:
            flash("Please provide feedback type and subject.", "error")
            return redirect(url_for("profile"))
        
        feedback_id = db.submit_feedback(
            username=username,
            feedback_type=feedback_type,
            subject=subject,
            original=original_text,
            corrected=corrected_text,
            description=description
        )
        
        logging.info("Feedback #%d submitted by %s: %s - %s", feedback_id, username, feedback_type, subject)
        flash("Thank you! Your feedback has been submitted successfully.", "success")
        
    except Exception as e:
        logging.exception("Failed to submit feedback")
        flash("Sorry, there was an error submitting your feedback. Please try again.", "error")
    
    return redirect(url_for("profile"))


@app.route("/feedback-admin")
def feedback_admin():
    """Admin view to review all feedback submissions"""
    username = session.get("username")
    if not username:
        return redirect(url_for("login"))
    
    # Check if user is admin
    is_admin = username in ["admin", "radiologist"]
    if not is_admin:
        flash("Access denied. Admin privileges required.", "error")
        return redirect(url_for("profile"))
    
    # Get filter status from query params
    status_filter = request.args.get("status", "pending")
    if status_filter == "all":
        all_feedback = db.get_all_feedback()
    else:
        all_feedback = db.get_all_feedback(status=status_filter)
    
    return render_template("feedback_admin.html", feedback_list=all_feedback, status_filter=status_filter)


@app.route("/review-feedback/<int:feedback_id>", methods=["POST"])
def review_feedback(feedback_id):
    """Admin action to approve/reject feedback"""
    username = session.get("username")
    if not username:
        return redirect(url_for("login"))
    
    # Check if user is admin
    is_admin = username in ["admin", "radiologist"]
    if not is_admin:
        flash("Access denied. Admin privileges required.", "error")
        return redirect(url_for("feedback_admin"))
    
    try:
        status = request.form.get("status", "").strip()
        admin_notes = request.form.get("admin_notes", "").strip()
        
        if status not in ["approved", "rejected", "implemented"]:
            flash("Invalid status.", "error")
            return redirect(url_for("feedback_admin"))
        
        db.update_feedback_status(
            feedback_id=feedback_id,
            status=status,
            reviewed_by=username,
            admin_notes=admin_notes
        )
        
        logging.info("Feedback #%d reviewed by %s: %s", feedback_id, username, status)
        flash(f"Feedback #{feedback_id} marked as {status}.", "success")
        
    except Exception as e:
        logging.exception("Failed to review feedback")
        flash("Sorry, there was an error processing your request.", "error")
    
    return redirect(url_for("feedback_admin"))


@app.route("/contact-support", methods=["POST"])
def contact_support():
    """Handle contact support form submission"""
    try:
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        message = request.form.get("message", "").strip()
        
        # Log the support request (in production, send email or save to database)
        logging.info("Support request from %s (%s): %s - %s", name, email, subject, message)
        
        flash("Thank you for contacting us! We'll get back to you soon.", "success")
    except Exception as e:
        logging.exception("Failed to process support request")
        flash("Sorry, there was an error submitting your message. Please try again.", "error")
    
    return redirect(url_for("help_page"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            session["username"] = username
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if db.get_user_by_username(username):
            flash("Username already exists. Please choose a different one.", "error")
        else:
            password_hash = generate_password_hash(password)
            db.create_user(username, password_hash)
            flash("Account created successfully. Please log in.", "success")
            return redirect(url_for("login"))
    return render_template("signup.html")


@app.route("/logout")
def logout():
    session.clear()  # Clear entire session instead of just username
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    # Use app.run only for local dev. For prod use a WSGI server.
    app.run(debug=True)
