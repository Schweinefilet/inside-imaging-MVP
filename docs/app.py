# app.py
import os
import io
import re
import json
import logging

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
)
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from flask_cors import CORS

# local db
from src import db

load_dotenv()

# --- logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# --- app ---
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

# CORS
CORS(app, resources={r"/*": {"origins": os.getenv("CORS_ORIGINS", "https://schweinefilet.github.io")}})

# available languages
LANGUAGES = ["English", "Kiswahili"]

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
    stats = {"total": 0, "male": 0, "female": 0, "0-17": 0, "18-30": 0, "31-50": 0, "51-65": 0, "66+": 0}
    return render_template("index.html", stats=stats, languages=LANGUAGES)


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        stats = {"total": 0, "male": 0, "female": 0, "0-17": 0, "18-30": 0, "31-50": 0, "51-65": 0, "66+": 0}
        return render_template("index.html", stats=stats, languages=LANGUAGES)

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
    patient = {
        "hospital": S.get("hospital", ""),
        "study": S.get("study", "Unknown"),
        "name": S.get("name", ""),
        "sex": S.get("sex", ""),
        "age": S.get("age", ""),
        "date": S.get("date", ""),
    }
    study = {"organ": patient.get("study") or "Unknown"}
    structured = S

    # Simple report stats for UI
    high_html = (S.get("findings", "") or "") + (S.get("conclusion", "") or "")
    report_stats = {
        "words": len((extracted or "").split()),
        "sentences": len(re.findall(r"[.!?]+", extracted or "")),
        "highlights_positive": high_html.count('class="positive"'),
        "highlights_negative": high_html.count('class="negative"'),
    }

    # persist for later pages like /payment and PDF download
    session["structured"] = structured
    session["patient"] = patient
    session["language"] = lang

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


@app.route("/language")
def language():
    return render_template("language.html")


@app.route("/report_status")
def report_status():
    return render_template("report_status.html")


@app.route("/payment")
def payment():
    # supply context expected by template
    structured = session.get("structured")
    if not isinstance(structured, dict):
        structured = {"report_type": "CT Scan", "price": "24.99"}
    lang = session.get("language", "English")
    return render_template("payment.html", structured=structured, language=lang)


@app.route("/help")
def help_page():
    return render_template("help.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
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
        username = request.form.get("username", "")
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
    session.pop("username", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    # Use app.run only for local dev. For prod use a WSGI server.
    app.run(debug=True)
