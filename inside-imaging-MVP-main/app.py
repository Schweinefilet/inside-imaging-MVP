"""Flask application entry point for Inside Imaging.

This app allows users to upload radiology reports (PDFs or images) or
paste report text, extract relevant information, simplify the findings
into lay terminology, and display the results on a separate page. It also
provides an API endpoint for programmatic use.

Note: To enable ChatGPT-based summarization, you would need to integrate
an API call to a language model within the build_structured function in
src/translate.py. This sample does not perform any remote API calls.
"""

from flask import Flask, request, render_template, jsonify, redirect, url_for, flash, session
from pathlib import Path
from werkzeug.utils import secure_filename
from src.translate import Glossary, build_structured
from src.extract import extract
from src import db
from werkzeug.security import generate_password_hash, check_password_hash
import os
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = Flask(__name__)
app.secret_key = "dev"
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20 MB upload limit

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Initialize the database and ensure tables exist
db.init_db()

# Create a default admin user if none exist
def ensure_default_user():
    user = db.get_user_by_username("admin")
    if user is None:
        # Create a default admin user with password 'password'. This should be
        # changed by the deployer immediately after deployment.
        pw_hash = generate_password_hash("password")
        db.create_user("admin", pw_hash)

ensure_default_user()

# Load the lay glossary once at startup
LAY_GLOSS = Glossary.load(Path("data/lay_glossary.csv"))

# Available languages for report output
LANGUAGES = ["English", "Swahili", "French", "Spanish"]


# Allowed extensions for uploads
ALLOWED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".txt"}


@app.get("/")
def index():
    """Render the home page with forms for uploading or pasting text.

    Requires login. Displays statistics in the sidebar and provides
    language options for the user to select the desired output language.
    """
    if not session.get("user_id"):
        return redirect(url_for("login"))
    stats = db.get_stats()
    return render_template(
        "index.html",
        stats=stats,
        languages=LANGUAGES,
    )


@app.get("/login")
def login():
    """Display the login form."""
    return render_template("login.html")


@app.post("/login")
def login_post():
    """Handle user login submission."""
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    user = db.get_user_by_username(username)
    if user and check_password_hash(user["password_hash"], password):
        session["user_id"] = user["id"]
        return redirect(url_for("index"))
    flash("Invalid username or password.")
    return redirect(url_for("login"))


@app.get("/logout")
def logout():
    """Log the user out and redirect to the login page."""
    session.clear()
    return redirect(url_for("login"))


@app.post("/paste")
def paste():
    """Handle submission of pasted text and display the simplified report."""
    if not session.get("user_id"):
        return redirect(url_for("login"))
    text = (request.form.get("text") or "").strip()
    lang = (request.form.get("language") or "English").strip()
    # Pass language to the report builder to allow multilingual support
    S = build_structured(text, LAY_GLOSS, language=lang)
    # Persist the record with the selected language
    S["language"] = lang
    db.add_patient_record(S)
    patient = {k: S.get(k, "") for k in ["hospital", "study", "name", "sex", "age", "date"]}
    structured = {k: S.get(k, "") for k in ["reason", "technique", "findings", "conclusion", "concern"]}
    return render_template(
        "result.html",
        patient=patient,
        structured=structured,
        extracted=text,
        language=lang,
        languages=LANGUAGES,
    )


@app.post("/upload")
def upload():
    """Handle file upload, extract text, simplify and show results."""
    if not session.get("user_id"):
        return redirect(url_for("login"))
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("No file chosen")
        return redirect(url_for("index"))
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        flash(f"Unsupported type: {ext}")
        return redirect(url_for("index"))
    lang = (request.form.get("language") or "English").strip()
    # Save the uploaded file to a temporary location
    safe_name = secure_filename(file.filename)
    tmp_path = UPLOAD_DIR / safe_name
    file.save(tmp_path)
    try:
        _kind, extracted = extract(tmp_path)
    finally:
        # Remove the temporary file regardless of success
        try:
            os.remove(tmp_path)
        except FileNotFoundError:
            pass
    # Build structured report with language for potential translation
    S = build_structured(extracted, LAY_GLOSS, language=lang)
    S["language"] = lang
    # Persist the record
    db.add_patient_record(S)
    patient = {k: S.get(k, "") for k in ["hospital", "study", "name", "sex", "age", "date"]}
    structured = {k: S.get(k, "") for k in ["reason", "technique", "findings", "conclusion", "concern"]}
    return render_template(
        "result.html",
        patient=patient,
        structured=structured,
        extracted=extracted,
        language=lang,
        languages=LANGUAGES,
    )


@app.post("/api/translate")
def api_translate():
    """API endpoint to translate a raw report into structured lay-language JSON."""
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()
    S = build_structured(text, LAY_GLOSS)
    patient = {k: S.get(k, "") for k in ["hospital", "study", "name", "sex", "age", "date"]}
    structured = {k: S.get(k, "") for k in ["reason", "technique", "findings", "conclusion", "concern"]}
    return jsonify({"patient": patient, "structured": structured, "extracted": text})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)