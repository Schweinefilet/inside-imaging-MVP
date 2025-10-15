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
* `app.py` – the main Flask server.  It provides login, upload/paste
  functionality and calls into `src/translate.py` for summarisation.

### Removing unused components

Earlier versions of this repository contained a separate FastAPI
backend under `backend/` and a React/Vite client under `frontend/`.
Those components are no longer required: the Flask app encapsulates
all functionality.  You can safely delete the `backend/` and
`frontend/` directories and the `.gh-pages` folder to avoid confusion
and reduce deployment size.  The zipped archives in the root of this
project were retained for reference and can also be removed.

To run the application locally, install the Python dependencies listed
in `requirements.txt` and start the Flask server:

```bash
pip install -r requirements.txt
FLASK_APP=app.py flask run
```
