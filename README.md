# Inside-Imaging

Inside Imaging is a small web application for converting radiology reports into simplified, lay‑friendly summaries and displaying them alongside a basic interactive body diagram. The primary entry point is `app.py`, a Flask application that uses the code in `src/` to parse reports, build structured summaries, and persist patient records.

## Architecture

* `src/` – shared utilities such as glossary‑based simplification, metadata extraction, SQLite helpers, and image/OCR handling.
* `templates/` and `static/` – HTML, CSS, and JavaScript used by the Flask app. The `result.html` template renders inline SVG diagrams for the body and brain, with in-template scripts such as `buildBodySVG`, `parseBrainLesion`, and `updateBrainDiagrams` that highlight study-specific regions and position lesion overlays based on structured report data passed from the server.
* `data/` – CSV files for the lay glossary and the SQLite database.
* `docs/` – static marketing assets that can be served from AWS alongside the core Flask service.
* `app.py` – the main Flask server. It provides login, upload/paste functionality and calls into `src/translate.py` for summarisation.

## Deployment

Production hosting now runs on AWS. The application is packaged from this repository and deployed to an AWS environment that serves the Flask application and static marketing assets. The former GitHub Pages workflow is deprecated; new deployments should target the AWS stack instead of GitHub Pages.

To run the application locally, install the Python dependencies listed in `requirements.txt` and start the Flask server:

```bash
pip install -r requirements.txt
FLASK_APP=app.py flask run
```

## Technology and skills overview

This project was built with a combination of technologies, languages, and techniques aimed at translating complex radiology reports into accessible summaries:

* **Languages & frameworks:** Python with Flask for the web server, Jinja2 for templating, HTML/CSS/JavaScript for the frontend, and SQLite for lightweight persistence.
* **Data processing & NLP:** Glossary-driven text simplification, metadata extraction utilities, and structured summarisation pipelines housed in `src/`.
* **Imaging & OCR:** Image uploads (PNG/JPG/TIFF/WEBP/BMP) are OCRed into text before summarisation. The app uses Tesseract via `pytesseract` and can be configured to leverage AWS OCR services where available.
* **Security & auth:** Basic login handling within `app.py` to protect patient data stored in the SQLite database.
* **DevOps & deployment:** Python dependency management via `requirements.txt`, Procfile-based process definitions, and AWS-backed deployment for production delivery of the Flask app and static assets.
* **Testing & QA:** Pytest configuration in `pytest.ini` with focused tests under `tests/` to validate parsing and translation logic.

## OCR for images

Image uploads (PNG/JPG/TIFF/WEBP/BMP) are OCRed into text and then passed to the translator.
Prerequisites:

- Install the Tesseract OCR engine on your system (e.g., Windows installer from UB Mannheim, macOS via `brew install tesseract`,
 Linux via your package manager).
- Ensure `pytesseract` is installed (included in `requirements.txt`).
- If Tesseract isn’t on your PATH, set `TESSERACT_CMD` to the full path of the executable, for example on Windows:

```
set TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe
```

The app will auto-detect image files on upload and extract text via Tesseract before summarization.
