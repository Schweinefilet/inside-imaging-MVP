import os, io, logging
from flask import Flask, render_template, request
from werkzeug.utils import secure_filename

# --- logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# --- app ---
app = Flask(__name__)

# --- translate wiring ---
try:
    from src.translate import Glossary, build_structured
except Exception as e:
    logging.exception("translate import failed")
    Glossary = None
    def build_structured(report_text: str, glossary=None, language: str = "English"):
        return {"reason":"","technique":"","findings":(report_text or "").strip(),"conclusion":"","concern":""}

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
    return render_template("index.html")

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "GET":
        return render_template("index.html")

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
        logging.info("summary_keys=%s", {k: len((S or {}).get(k) or "") for k in ("reason","technique","findings","conclusion","concern")})
    except Exception:
        logging.exception("build_structured failed")
        S = {"reason":"","technique":"","findings":"","conclusion":"","concern":""}

    # minimal study so template renders
    study = {"organ": "Unknown"}
    return render_template("result.html", S=S, study=study, language=lang)

if __name__ == "__main__":
    app.run(debug=True)
