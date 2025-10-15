import os
import io
import re
import json
import logging

from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from dotenv import load_dotenv
from flask_cors import CORS

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
    from src.translate import Glossary, build_structured
except Exception:
    logging.exception("translate import failed")
    Glossary = None

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


@app.route("/", methods=["GET"])
def index():
    stats = {
        "total": 0,
        "male": 0,
        "female": 0,
        "0-17": 0,
        "18-30": 0,
        "31-50": 0,
        "51-65": 0,
        "66+": 0,
    }
    return render_template("index.html", stats=stats, languages=LANGUAGES)


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        stats = {
            "total": 0,
            "male": 0,
            "female": 0,
            "0-17": 0,
            "18-30": 0,
            "31-50": 0,
            "51-65": 0,
            "66+": 0,
        }
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
                try:
                    from pdfminer_high_level import extract_text  # type: ignore
                except Exception:
                    # keep backward compat if module name differs
                    try:
                        from pdfminer.high_level import extract_text  # type: ignore
                    except Exception:
                        extract_text = None
                try:
                    extracted = extract_text(io.BytesIO(data)) if extract_text else ""
                except Exception:
                    logging.exception("pdfminer failed; extracted empty")
            else:
                try:
                    extracted = data.decode("utf-8", "ignore")
                except Exception:
                    logging.exception("decode failed; extracted empty")
        except Exception:
            logging.exception("file handling failed; extracted empty")

    logging.info("len(extracted)=%s", len(extracted or ""))
    try:
        logging.info("calling build_structured language=%s", lang)
        S = build_structured(extracted, LAY_GLOSS, language=lang)
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
        S=S,
        structured=structured,
        patient=patient,
        extracted=extracted,
        study=study,
        language=lang,
        report_stats=report_stats,
    )


@app.post("/download-pdf")
def download_pdf():
    """
    Generate a PDF of the report with logo top-left.
    Expects POST with hidden fields 'structured' and 'patient' (JSON),
    or falls back to session values.
    """
    # Prefer form payload so the user can download without relying on session
    try:
        structured = request.form.get("structured")
        patient = request.form.get("patient")
        if structured:
            structured = json.loads(structured)
        else:
            structured = session.get("structured", {})
        if patient:
            patient = json.loads(patient)
        else:
            patient = session.get("patient", {})
    except Exception:
        logging.exception("Failed to parse form JSON; falling back to session")
        structured = session.get("structured", {})
        patient = session.get("patient", {})

    # Render HTML to be converted
    html_str = render_template("pdf_report.html", structured=structured or {}, patient=patient or {})

    # Try WeasyPrint first
    try:
        from weasyprint import HTML  # type: ignore
        pdf_bytes = HTML(string=html_str, base_url=request.url_root).write_pdf()
        resp = make_response(pdf_bytes)
        resp.headers["Content-Type"] = "application/pdf"
        resp.headers["Content-Disposition"] = 'attachment; filename="inside-imaging-report.pdf"'
        return resp
    except Exception:
        logging.exception("WeasyPrint PDF render failed; returning HTML fallback")
        # Fallback: return HTML download so user still gets a file
        resp = make_response(html_str)
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        resp.headers["Content-Disposition"] = 'attachment; filename="inside-imaging-report.html"'
        return resp


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
    app.run(debug=True)
