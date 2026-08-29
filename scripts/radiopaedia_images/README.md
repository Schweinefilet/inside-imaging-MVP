# Radiopaedia image scraper (stale)

One-off tooling used during an earlier iteration to collect example medical
images from Radiopaedia and wire them into the anatomy explorer.

**Status: orphaned.** `update_image_urls.py` patches `static/organ-highlight.js`,
which was removed in commit `893b811`. The app now uses the static SVGs in
`static/images/anatomy/` instead. Nothing in the application reads any file in
this directory. Kept for reference / provenance — safe to delete.

| File | Role |
|------|------|
| `rp_image_links.py` | Scrapes article/case pages, writes `data/rp_image_links.csv`. |
| `find_remaining.py` | Second-pass scraper for conditions the first pass missed. |
| `update_image_urls.py` | Rewrote `imageUrl` entries in the (now-deleted) `static/organ-highlight.js`. |
| `data/rp_image_links.csv` | Scraper output. |
| `data/additional_urls.json`, `data/url_mapping*.json` | Hand-maintained URL overrides / normalized mapping. |

If revived, run from the project root and repoint the output/target paths at
whatever consumes them now.
