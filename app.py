# app.py
import os
import io
import re
import json
import logging

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
        "title": "Making MRI Findings Actionable for Patients",
        "summary": "How radiologists can translate technical impressions into patient-friendly plans without losing nuance.",
        "author": "Dr. Amina Hussein",
        "date": "January 15, 2025",
        "read_time": "6 min read",
        "url": "https://www.rsna.org/news/2024/september/patient-connections",
    },
    {
        "title": "AI Triage: What Clinicians Need to Know",
        "summary": "A practical framework for validating AI-assisted reads inside busy radiology departments.",
        "author": "Dr. Marc Feld",
        "date": "December 9, 2024",
        "read_time": "5 min read",
        "url": "https://www.diagnosticimaging.com/view/ai-in-radiology-five-takeaways",
    },
    {
        "title": "Ultrasound Rooms Built for Empathy",
        "summary": "Designing spaces and scripts that help expectant parents stay informed and calm during imaging.",
        "author": "Dr. Lillian Chen",
        "date": "November 28, 2024",
        "read_time": "4 min read",
        "url": "https://appliedradiology.com/articles/improving-patient-experience-in-ultrasound",
    },
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


@app.route("/", methods=["GET"])
def index():
    stats = db.get_stats()
    recent_reports = session.get("recent_reports", [])
    return render_template("index.html", stats=stats, languages=LANGUAGES, recent_reports=recent_reports)


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        stats = db.get_stats()
        recent_reports = session.get("recent_reports", [])
        return render_template("index.html", stats=stats, languages=LANGUAGES, recent_reports=recent_reports)

    file = request.files.get("file")
    lang = request.form.get("language", "English")
    file_text = request.form.get("file_text", "")
    extracted = ""

    # Prefer pasted text if provided
    if file_text and file_text.strip():
        extracted = file_text.strip()
    elif file and file.filename:
        fname = secure_filename(file.filename)
        data = file.read()
        try:
            if fname.lower().endswith(".pdf"):
                extracted = _extract_text_from_pdf_bytes(data)
            else:
                try:
                    extracted = data.decode("utf-8", "ignore")
                except Exception:
                    logging.exception("decode failed; extracted empty")
        except Exception:
            logging.exception("file handling failed; extracted empty")

    logging.info("len(extracted)=%s", len(extracted or ""))

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

    # persist for later pages like /payment and PDF download
    session["structured"] = structured
    session["patient"] = patient
    session["language"] = lang

    report_id = None
    try:
        report_id = db.store_report_event(patient, structured, report_stats, lang)
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

    return render_template(
        "result.html",
        S=structured,
        structured=structured,
        patient=patient,
        extracted="",
        study=study,
        language=language,
        report_stats=report_stats,
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

    html_str = render_template("pdf_report.html", structured=structured, patient=patient)

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


@app.route("/projects")
def projects():
    return render_template("projects.html")


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
    return render_template(
        "blogs.html",
        posts=BLOG_POSTS,
        submit_url="mailto:editor@insideimaging.example?subject=Radiologist%20Blog%20Pitch",
    )


@app.route("/report_status")
def report_status():
    stats = db.get_stats()
    return render_template("report_status.html", stats=stats)


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


@app.route("/profile")
def profile():
    return render_template("profile.html")


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
            return redirect(url_for("index"))
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
