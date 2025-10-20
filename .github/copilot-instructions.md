# Inside Imaging – AI Agent Playbook

## Project landmarks
- **Flask single-file app** lives in `app.py`; blueprints are not used. Routes render Jinja templates in `templates/` and serve static assets from `static/`.
- **Translation pipeline** is in `src/translate.py`. It strips PHI before calling OpenAI, builds simplified report bundles, and sets session state for later routes (`/payment`, `/download-pdf`). Respect its sanitisation helpers when changing input/output handling.
- **Front-end stack** is server-rendered HTML (`templates/*.html`) plus shared styling in `static/main.css` and page-specific CSS (e.g., `static/dashboard.css`, `static/magazine.css`). The navigation bar and theme switcher must stay visually consistent across templates.
- **Docs mirror**: `docs/index.html` is a static copy used by GitHub Pages. Whenever you update navbar links or hero content, mirror the change there.

## Configuration + environment
- Environment values (OpenAI keys, flags, model names) are read via `python-dotenv`. If no model is set, `_resolve_models()` defaults to `gpt-5` with a `gpt-4o-mini` fallback. Keep JSON-mode compatibility when swapping models.
- WeasyPrint is optional. `_pdf_response_from_html` assumes it is installed; if you add PDF features, guard imports the same way.
- `MAGAZINE_ISSUES` and `BLOG_POSTS` in `app.py` seed the magazine viewer and blog pages. Relative paths under `static/` are resolved to URLs at request time.

## Running + testing
- Local dev server: `python app.py` (Flask debug mode enabled). No Flask CLI or gunicorn configs exist.
- Tests: `pytest` only. Currently `tests/test_smoke.py` is a placeholder; add focused tests alongside new modules.

## Implementation patterns
- **Session data contract**: `/upload` stores `structured`, `patient`, and `language` in the Flask session. Downstream pages rely on these keys—recompute or clear them carefully.
- **HIPAA compliance**: `src/translate.py` performs redaction before external API calls. Do not bypass `_scrub_phi` or reuse the raw report outside that module.
- **Navbar + theme**: All templates embed the same `<header class="navbar">` markup and slider-based theme switcher. When touching nav links, update every template plus `docs/index.html`.
- **Styling**: Dark theme is a true-black base with flat mint accents (see `static/main.css`). Avoid reintroducing glossy gradients; reuse `var(--mint)` and `var(--mint-soft)` tokens. Buttons across feature-specific stylesheets should match the flattened theme.
- **Static assets**: Large media (e.g., magazine PDFs) live under `static/magazine/`. Use `url_for('static', filename=...)` when referencing them to keep mirrors working.

## Contribution etiquette
- Maintain ASCII-only files unless a template already mixes encodings.
- Add explanatory comments only for non-obvious logic (e.g., PHI handling, WeasyPrint fallbacks).
- Keep `LANGUAGES` consistent with available translations; updating it affects UI menus and translation prompts.
- When adding routes, stay within `app.py` unless there is a compelling reason to modularise—tests and deployment assume the current structure.

Please let me know if any part of these instructions feels unclear or incomplete so we can refine them. 