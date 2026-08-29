"""Mechanical Tier-1 template converter.

For each standalone template, rewrite it to extend base.html:
  - drop doctype, head, prepaint script, duplicated navbar, theme.js script tag
  - move <title> into {% block title %}
  - move per-page <link rel="stylesheet"> and <style> into {% block extra_css %}
  - rename <main class="content ..."> to <div class="content ...">
  - drop {% include '_footer.html' %} (base.html handles footer)
  - wrap remaining page-bottom scripts into {% block extra_js %}

Run from repo root:
    python3 scripts/convert_templates.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

TEMPLATES_DIR = Path("templates")

TARGETS = [
    "profile.html",
    "report_status.html",
    "team.html",
    "help.html",
    "blogs.html",
    "blogs_full.html",
    "login.html",
    "signup.html",
    "language.html",
    "payment.html",
    "feedback_admin.html",
    "result.html",
]

TITLE_MAP = {
    "profile.html": "Profile",
    "report_status.html": "Statistics",
    "team.html": "Our Team",
    "help.html": "Help",
    "blogs.html": "Insights",
    "blogs_full.html": "Insights",
    "login.html": "Sign In",
    "signup.html": "Sign Up",
    "language.html": "Magazine",
    "payment.html": "Payment",
    "feedback_admin.html": "Feedback Admin",
    "result.html": "Report Result",
}


def extract_title(src: str) -> str:
    m = re.search(r"<title>([^<]+)</title>", src)
    return m.group(1).strip() if m else "Inside Imaging"


def extract_head_links_and_styles(src: str) -> str:
    """Return per-page CSS link tags and inline <style> blocks (excluding main.css)."""
    head_match = re.search(r"<head[^>]*>(.*?)</head>", src, re.DOTALL)
    if not head_match:
        return ""
    head = head_match.group(1)

    keep_parts: list[str] = []

    # Keep stylesheet links other than main.css (base.html provides main.css)
    for link in re.findall(r"<link\s+rel=\"stylesheet\"[^>]*>", head):
        if "main.css" in link or "loader.css" in link:
            continue
        if "logo.svg" in link:  # favicon — base.html handles it
            continue
        keep_parts.append(link.strip())

    # Keep inline <style> blocks
    for style in re.findall(r"<style[^>]*>.*?</style>", head, re.DOTALL):
        keep_parts.append(style.strip())

    return "\n".join(keep_parts)


def strip_doctype_and_head(src: str) -> str:
    """Remove everything from <!doctype html> through <body...> opening."""
    m = re.search(r"<body[^>]*>", src)
    if not m:
        return src
    return src[m.end():].lstrip("\n")


def strip_header_shell(src: str) -> str:
    """Remove <div class=\"page-wrapper\"> opening, <div class=\"header-shell\">…</div> (navbar),
    plus the outer page-wrapper closing </div> later in the file.

    Strategy: locate the start of <div class="header-shell"> and the FIRST <main
    that follows; delete everything between (exclusive of <main>). Then strip
    any leading <div class="page-wrapper"> that appeared just before.
    """
    # 1. Find start of header-shell
    hs_match = re.search(r"<div class=\"header-shell\">", src)
    if not hs_match:
        return src
    # 2. Find next <main… that begins the page content
    main_match = re.search(r"<main\b", src[hs_match.end():])
    if not main_match:
        return src
    hs_end_in_src = hs_match.end() + main_match.start()

    # 3. Find any opening <div class="page-wrapper"> just before header-shell and strip it too
    prefix = src[:hs_match.start()]
    pw_match = re.search(r"<div class=\"page-wrapper\">\s*\n\s*$", prefix)
    if pw_match:
        prefix = prefix[:pw_match.start()]

    return prefix + src[hs_end_in_src:]


def convert_main_to_div(src: str) -> str:
    """Rename <main class="content ..."> → <div class="content ..."> and matching </main>.
    Only converts the first such pair, which is the page's main content wrapper."""
    open_match = re.search(r"<main(\s+class=\"[^\"]*content[^\"]*\")[^>]*>", src)
    if not open_match:
        # Try <main class="..."> with any class — used by e.g. blogs_full.html (<main class="blogs-full">)
        open_match = re.search(r"<main(\s+class=\"[^\"]*\")[^>]*>", src)
    if not open_match:
        return src

    open_start, open_end = open_match.span()
    new_open = "<div" + open_match.group(1) + ">"

    # Locate the matching </main> after open_end
    close_idx = src.find("</main>", open_end)
    if close_idx == -1:
        return src

    return (
        src[:open_start]
        + new_open
        + src[open_end:close_idx]
        + "</div>"
        + src[close_idx + len("</main>"):]
    )


def strip_footer_include(src: str) -> str:
    return re.sub(r"\s*{%\s*include\s+['\"]_footer\.html['\"]\s*%}\s*\n", "\n", src)


def strip_page_wrapper_close(src: str) -> str:
    """Remove the trailing </div> that closed <div class="page-wrapper">."""
    # The page-wrapper close is typically just after the footer include we stripped.
    # We remove the FIRST </div> on a line by itself before the first <script tag.
    script_idx = src.find("<script")
    if script_idx == -1:
        script_idx = len(src)
    head = src[:script_idx]
    tail = src[script_idx:]
    head = re.sub(r"\n\s*</div>\s*\n(\s*\n)?$", "\n", head)
    return head + tail


def strip_theme_and_loader_scripts(src: str) -> str:
    src = re.sub(
        r"\s*<script\s+src=\"{{\s*url_for\('static',\s*filename='theme\.js'\)[^\"]*\"\s*></script>\s*\n",
        "\n",
        src,
    )
    src = re.sub(
        r"\s*<script\s+src=\"{{\s*url_for\('static',\s*filename='loader\.js'\)[^\"]*\"\s*></script>\s*\n",
        "\n",
        src,
    )
    src = re.sub(
        r"\s*<script\s+src=\"/static/loader\.js\"\s*></script>\s*\n",
        "\n",
        src,
    )
    return src


def strip_body_html_close(src: str) -> str:
    return re.sub(r"\s*</body>\s*</html>\s*\Z", "\n", src)


def split_body_and_trailing_scripts(src: str) -> tuple[str, str]:
    """Split the body content from any trailing <script> tags that should
    move to {% block extra_js %}.

    We treat everything from the LAST </div> (matching our converted <div class="content...">)
    forward as candidate for extra_js. If no <script> tags are present, return (src, "").
    """
    # Find the last </div> in the file
    last_div_close = src.rfind("</div>")
    if last_div_close == -1:
        return src, ""

    body = src[:last_div_close + len("</div>")]
    rest = src[last_div_close + len("</div>"):]

    # rest may contain newlines + <script>…</script> blocks
    if "<script" not in rest:
        return body, ""

    return body, rest.strip()


def convert_one(path: Path) -> tuple[bool, str]:
    """Convert one template. Return (changed, message)."""
    src = path.read_text(encoding="utf-8")

    if src.lstrip().startswith("{% extends"):
        # blogs_full.html: already extends but has an outdated inline navbar to strip
        # Replace its inline header-shell with nothing (base.html provides nav)
        new = re.sub(
            r"<div class=\"header-shell\">.*?</div>\s*\n",
            "",
            src,
            count=1,
            flags=re.DOTALL,
        )
        # Also rename <main class="..."> to <div class="...">
        new = convert_main_to_div(new)
        if new == src:
            return False, "already converted; no inline navbar found"
        path.write_text(new, encoding="utf-8")
        return True, "stripped inline navbar from already-extending template"

    title_label = TITLE_MAP.get(path.name) or extract_title(src).replace(" - Inside Imaging", "").strip()
    extra_css_block = extract_head_links_and_styles(src)

    body = strip_doctype_and_head(src)
    body = strip_header_shell(body)
    body = convert_main_to_div(body)
    body = strip_theme_and_loader_scripts(body)
    body = strip_footer_include(body)
    body = strip_body_html_close(body)
    body = strip_page_wrapper_close(body)

    body_content, trailing_scripts = split_body_and_trailing_scripts(body)

    # Compose final template
    parts: list[str] = []
    parts.append('{% extends "base.html" %}\n')
    parts.append(f"{{% block title %}}{title_label} · Inside Imaging{{% endblock %}}\n")
    if extra_css_block:
        parts.append("{% block extra_css %}")
        parts.append(extra_css_block)
        parts.append("{% endblock %}\n")
    parts.append("{% block content %}")
    parts.append(body_content.strip("\n"))
    parts.append("{% endblock %}")

    if trailing_scripts:
        parts.append("\n{% block extra_js %}")
        parts.append(trailing_scripts)
        parts.append("{% endblock %}")

    new_text = "\n".join(parts) + "\n"
    path.write_text(new_text, encoding="utf-8")
    return True, f"converted ({len(body_content)} body bytes, {'+scripts' if trailing_scripts else 'no scripts'})"


def main() -> int:
    failures = 0
    for name in TARGETS:
        path = TEMPLATES_DIR / name
        if not path.exists():
            print(f"SKIP {name}: not found")
            continue
        try:
            changed, msg = convert_one(path)
            print(f"{'OK  ' if changed else 'SKIP'} {name}: {msg}")
        except Exception as e:
            failures += 1
            print(f"FAIL {name}: {type(e).__name__}: {e}")
    return failures


if __name__ == "__main__":
    sys.exit(main())
