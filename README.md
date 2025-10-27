# Inside-Imaging
Inside Imaging is a small web application for converting radiology
reports into simplified, lay‑friendly summaries and displaying them
alongside a basic interactive body diagram.  The primary entry point
is `app.py`, a Flask application that uses the code in `src/` to
parse reports, build structured summaries and persist patient records.

### Architecture

* `src/` – shared utilities such as glossary‑based simplification,
  metadata extraction and SQLite database helpers.  This is the
  authoritative implementation for summarising reports.
* `templates/` and `static/` – the HTML, CSS and JavaScript used by
  the Flask app.  The `result.html` template renders inline SVG
  diagrams for the body and brain, with in-template scripts such as
  `buildBodySVG`, `parseBrainLesion` and `updateBrainDiagrams` that
  highlight study-specific regions and position lesion overlays based
  on the structured report data passed from the server.
* `data/` – CSV files for the lay glossary and the SQLite database.
* `docs/` – the lightweight static marketing page that GitHub Pages
  serves.  A workflow keeps the assets in `docs/static/` aligned with
  the main Flask styles on every push to `main`.
* `app.py` – the main Flask server.  It provides login, upload/paste
  functionality and calls into `src/translate.py` for summarisation.
### GitHub Pages

The repository includes a GitHub Actions workflow at
`.github/workflows/pages.yml` that deploys the contents of `docs/` to
GitHub Pages whenever `main` is updated.  The workflow rebuilds
`docs/static/` from the source `static/` directory so that the marketing
site mirrors the latest styles automatically.  You can also trigger the
workflow manually from the Actions tab if you need to redeploy without
making a commit.

To run the application locally, install the Python dependencies listed
in `requirements.txt` and start the Flask server:

```bash
pip install -r requirements.txt
FLASK_APP=app.py flask run
```

### OCR for images

Image uploads (PNG/JPG/TIFF/WEBP/BMP) are OCRed into text and then passed to the translator.
Prerequisites:

- Install the Tesseract OCR engine on your system (e.g., Windows installer from UB Mannheim, macOS via `brew install tesseract`, Linux via your package manager).
- Ensure `pytesseract` is installed (included in `requirements.txt`).
- If Tesseract isn’t on your PATH, set `TESSERACT_CMD` to the full path of the executable, for example on Windows:

```
set TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe
```

The app will auto-detect image files on upload and extract text via Tesseract before summarization.
