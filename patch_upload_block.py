import io, re, sys

PATH = "app.py"
src  = io.open(PATH, "r", encoding="utf-8").read()

# find the /upload route block
m = re.search(r'@app\.route\("/upload"[^)]*\)\s*def upload\([^\)]*\):', src)
if not m:
    print("ERROR: /upload route not found"); sys.exit(2)
start = m.start()

# end at the next decorator or EOF
m2 = re.search(r'\n@app\.route\(', src[m.end():])
end = (m.end() + m2.start()) if m2 else len(src)

block = r'''
@app.route("/upload", methods=["GET", "POST"])
def upload():
    import logging, os, io
    from flask import request, render_template
    from werkzeug.utils import secure_filename

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
                    logging.exception("pdf text extraction failed; empty")
                    extracted = ""
            else:
                try:
                    extracted = data.decode("utf-8", "ignore")
                except Exception:
                    extracted = ""
        except Exception:
            logging.exception("file handling failed")
            extracted = ""

    logging.info("len(extracted)=%s", len(extracted or ""))
    try:
        logging.info("calling build_structured language=%s", lang)
        S = build_structured(extracted, LAY_GLOSS, language=lang)
        logging.info("summary_keys=%s", {k: len(S.get(k) or "") for k in ("reason","technique","findings","conclusion","concern")})
    except Exception:
        logging.exception("build_structured failed")
        S = {"reason":"","technique":"","findings":"","conclusion":"","concern":""}

    # Minimal 'study' so template renders even without metadata
    study = {"organ": "Unknown"}

    return render_template("result.html", S=S, study=study, language=lang)
'''.lstrip("\n")

new = src[:start] + block + ("\n" if not src[end:].startswith("\n") else "") + src[end:]
io.open(PATH, "w", encoding="utf-8", newline="").write(new)
print("PATCHED /upload")
