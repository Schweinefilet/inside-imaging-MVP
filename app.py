import os
import io
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from flask_cors import CORS
from src import db

# Load environment variables
load_dotenv()

# --- logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# --- app ---
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": os.getenv("CORS_ORIGINS", "https://schweinefilet.github.io")}})

# available languages
LANGUAGES = ["English", "Kiswahili"]
# Secret key for session management
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")

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

    extracted = ""
    if file and file.filename:
        fname = secure_filename(file.filename)
        data = file.read()
        try:
            if fname.lower().endswith(".pdf"):
                try:
                    from pdfminer.high_level import extract_text
                    extracted = extract_text(io.BytesIO(data)) or ""
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

    # minimal study so template renders
    study = {"organ": "Unknown"}

    # Provide a placeholder patient object so the template never errors.
    patient = {
        "hospital": "",
        "study": study.get("organ", "Unknown"),
        "name": "",
        "sex": "",
        "age": "",
        "date": "",
    }

    # Alias the structured summary for the template
    structured = S

    # Also pass the raw extracted text for the "Extracted text" details section
    return render_template(
        "result.html",
        S=S,
        structured=structured,
        patient=patient,
        extracted=extracted,
        study=study,
        language=lang,
    )


@app.route("/language")
def language():
    """Render the language selection page"""
    return render_template("language.html")


@app.route("/report_status")
def report_status():
    """Render the report status page"""
    return render_template("report_status.html")


@app.route("/payment")
def payment():
    """Render the payment page"""
    return render_template("payment.html")


@app.route("/help")
def help_page():
    """Render the help page"""
    return render_template("help.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """User login route"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = db.get_user_by_username(username)
        if user and check_password_hash(user["password_hash"], password):
            session["username"] = username
            flash("Logged in successfully.", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password.", "error")
    return render_template("login.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    """User signup route"""
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        # Check if user exists
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
    """Log out the current user"""
    session.pop("username", None)
    flash("Logged out successfully.", "success")
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True)
