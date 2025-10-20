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
  the Flask app.  The `result.html` template contains a Three.js
  viewer that highlights the approximate location of the organ being
  scanned based on the study name passed from the server.
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
