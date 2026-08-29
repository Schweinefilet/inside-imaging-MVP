"""
rp_image_links.py

Goal:
- For each condition in predefined categories, find Radiopaedia article or case pages.
- On a page, collect ONLY images whose captions include the word "Case".
- Follow each /cases/ link found on an article’s "Cases and figures" cards.
- From each case page, extract multiple CDN image URLs:
  https://prod-images-static.radiopaedia.org/images/...

Outputs:
- Prints results to console.
- Writes a CSV with columns: category, condition, page_url, image_url, index, status.

Run:
  python -m pip install requests beautifulsoup4 cloudscraper
  python rp_image_links.py --max-images 30 --csv rp_image_links.csv
"""

import csv
import re
import time
import random
import argparse
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

# -------------------------- config --------------------------

DEFAULT_MAX_IMAGES = 20
DEFAULT_OUT_CSV = "rp_image_links.csv"

BASE = "https://radiopaedia.org"

CATEGORIES = {
    "Kidney & Urinary": [
        "Kidney stones", "Hydronephrosis", "Renal cell carcinoma",
        "Nephrolithiasis", "Bladder stone", "Renal cyst",
        "Polycystic kidney disease"
    ],
    "Respiratory/Lung": [
        "Pleural effusion", "Pneumonia", "Pulmonary edema",
        "Atelectasis", "Emphysema", "Pulmonary fibrosis",
        "Pulmonary embolism", "Pneumothorax", "ARDS"
    ],
    "Cardiovascular": [
        "Enlarged heart", "Aortic aneurysm", "Aortic dissection",
        "Pericardial effusion", "Carotid stenosis",
        "Deep vein thrombosis", "Portal vein thrombosis",
        "Portal hypertension", "Budd-Chiari syndrome"
    ],
    "Brain & Neurological": [
        "Brain tumor", "Stroke", "Brain hemorrhage",
        "Subdural hematoma", "Epidural hematoma",
        "Subarachnoid hemorrhage", "Hydrocephalus",
        "Multiple sclerosis", "Acoustic neuroma",
        "Chiari malformation", "Syringomyelia"
    ],
    "Liver & Biliary": [
        "Liver cyst", "Cirrhosis", "Fatty liver", "Hepatomegaly",
        "Liver metastases", "Hepatocellular carcinoma",
        "Cholecystitis", "Gallstones", "Choledocholithiasis",
        "Biliary obstruction"
    ],
    "Gastrointestinal": [
        "Appendicitis", "Bowel obstruction", "Diverticulitis",
        "Pneumoperitoneum", "Esophageal cancer", "Gastric cancer",
        "Colon cancer", "Crohn's disease", "Ulcerative colitis",
        "Intussusception", "Volvulus", "Mesenteric ischemia",
        "Pneumatosis intestinalis"
    ],
    "Musculoskeletal/Spine": [
        "Fractures (general)", "Hip fracture", "Scaphoid fracture",
        "Vertebral compression fracture", "Rib fracture",
        "Clavicle fracture", "Orbital fracture", "Scoliosis",
        "Osteomyelitis", "Osteoarthritis", "Cervical spondylosis",
        "Spinal stenosis", "Herniated disc", "Spondylolisthesis",
        "Ankylosing spondylitis"
    ],
    "Soft Tissue/Joints": [
        "Rotator cuff tear", "Meniscal tear", "ACL tear",
        "Achilles tendon rupture"
    ],
    "Endocrine": [
        "Thyroid nodule", "Thyroid goiter", "Parathyroid adenoma",
        "Adrenal adenoma", "Pheochromocytoma",
        "Cushing syndrome (pituitary adenoma)"
    ],
    "Reproductive": [
        "Ovarian cyst", "Uterine fibroids",
        "Prostate enlargement (BPH)", "Testicular torsion"
    ],
    "Oncology/Cancer": [
        "Tumor (general)", "Lymphoma", "Metastases", "Breast cancer",
        "Pancreatic cancer"
    ],
    "Other Organs": [
        "Splenomegaly", "Splenic rupture", "Ascites", "Sinusitis",
        "Pancreatitis", "UTI/Pyelonephritis", "Inguinal hernia",
        "Abdominal aortic calcification"
    ],
}

SEED_SLUGS = {
    # Kidney & Urinary
    "Kidney stones": ["renal-calculi", "renal-stones", "nephrolithiasis"],
    "Hydronephrosis": ["hydronephrosis"],
    "Renal cell carcinoma": ["renal-cell-carcinoma"],
    "Nephrolithiasis": ["nephrolithiasis", "renal-calculi"],
    "Bladder stone": ["vesical-calculus", "bladder-stone", "urinary-bladder-calculi"],
    "Renal cyst": ["renal-cyst"],
    "Polycystic kidney disease": ["autosomal-dominant-polycystic-kidney-disease", "polycystic-kidney-disease"],

    # Respiratory/Lung
    "Pleural effusion": ["pleural-effusion"],
    "Pneumonia": ["pneumonia"],
    "Pulmonary edema": ["pulmonary-oedema", "pulmonary-edema"],
    "Atelectasis": ["atelectasis"],
    "Emphysema": ["emphysema"],
    "Pulmonary fibrosis": ["pulmonary-fibrosis"],
    "Pulmonary embolism": ["pulmonary-embolism"],
    "Pneumothorax": ["pneumothorax"],
    "ARDS": ["acute-respiratory-distress-syndrome"],

    # Cardiovascular
    "Enlarged heart": ["cardiomegaly"],
    "Aortic aneurysm": ["abdominal-aortic-aneurysm", "thoracic-aortic-aneurysm", "aortic-aneurysm"],
    "Aortic dissection": ["aortic-dissection"],
    "Pericardial effusion": ["pericardial-effusion"],
    "Carotid stenosis": ["carotid-artery-stenosis"],
    "Deep vein thrombosis": ["deep-venous-thrombosis", "deep-vein-thrombosis"],
    "Portal vein thrombosis": ["portal-vein-thrombosis"],
    "Portal hypertension": ["portal-hypertension"],
    "Budd-Chiari syndrome": ["budd-chiari-syndrome"],

    # Brain & Neuro
    "Brain tumor": ["brain-tumour", "brain-tumor"],
    "Stroke": ["acute-ischaemic-stroke", "ischemic-stroke"],
    "Brain hemorrhage": ["intracerebral-haemorrhage", "intracerebral-hemorrhage", "intracranial-haemorrhage"],
    "Subdural hematoma": ["subdural-haematoma", "subdural-hematoma"],
    "Epidural hematoma": ["epidural-haematoma", "epidural-hematoma"],
    "Subarachnoid hemorrhage": ["subarachnoid-haemorrhage", "subarachnoid-hemorrhage"],
    "Hydrocephalus": ["hydrocephalus"],
    "Multiple sclerosis": ["multiple-sclerosis"],
    "Acoustic neuroma": ["vestibular-schwannoma", "acoustic-neuroma"],
    "Chiari malformation": ["chiari-i-malformation", "chiari-malformation"],
    "Syringomyelia": ["syringomyelia"],

    # Liver & Biliary
    "Liver cyst": ["hepatic-cyst", "liver-cyst"],
    "Cirrhosis": ["cirrhosis"],
    "Fatty liver": ["hepatic-steatosis", "fatty-liver"],
    "Hepatomegaly": ["hepatomegaly"],
    "Liver metastases": ["liver-metastases", "hepatic-metastases"],
    "Hepatocellular carcinoma": ["hepatocellular-carcinoma"],
    "Cholecystitis": ["acute-cholecystitis", "cholecystitis"],
    "Gallstones": ["cholelithiasis", "gallstones"],
    "Choledocholithiasis": ["choledocholithiasis"],
    "Biliary obstruction": ["biliary-obstruction", "obstructive-jaundice"],

    # GI
    "Appendicitis": ["acute-appendicitis"],
    "Bowel obstruction": ["small-bowel-obstruction", "bowel-obstruction"],
    "Diverticulitis": ["diverticulitis"],
    "Pneumoperitoneum": ["pneumoperitoneum"],
    "Esophageal cancer": ["oesophageal-carcinoma", "esophageal-carcinoma"],
    "Gastric cancer": ["gastric-carcinoma", "stomach-cancer"],
    "Colon cancer": ["colorectal-carcinoma", "colon-carcinoma"],
    "Crohn's disease": ["crohn-disease", "crohns-disease"],
    "Ulcerative colitis": ["ulcerative-colitis"],
    "Intussusception": ["intussusception"],
    "Volvulus": ["sigmoid-volvulus", "midgut-volvulus", "volvulus"],
    "Mesenteric ischemia": ["acute-mesenteric-ischemia", "mesenteric-ischaemia"],
    "Pneumatosis intestinalis": ["pneumatosis-intestinalis"],

    # MSK/Spine
    "Fractures (general)": ["fracture"],
    "Hip fracture": ["hip-fracture", "neck-of-femur-fracture"],
    "Scaphoid fracture": ["scaphoid-fracture"],
    "Vertebral compression fracture": ["vertebral-compression-fracture"],
    "Rib fracture": ["rib-fracture"],
    "Clavicle fracture": ["clavicle-fracture", "clavicular-fracture"],
    "Orbital fracture": ["orbital-blowout-fracture", "orbital-fracture"],
    "Scoliosis": ["scoliosis"],
    "Osteomyelitis": ["osteomyelitis"],
    "Osteoarthritis": ["osteoarthritis"],
    "Cervical spondylosis": ["cervical-spondylosis"],
    "Spinal stenosis": ["spinal-canal-stenosis", "lumbar-spinal-stenosis"],
    "Herniated disc": ["disc-herniation", "prolapsed-intervertebral-disc"],
    "Spondylolisthesis": ["spondylolisthesis"],
    "Ankylosing spondylitis": ["ankylosing-spondylitis"],

    # Soft tissue/joints
    "Rotator cuff tear": ["rotator-cuff-tear"],
    "Meniscal tear": ["meniscal-tear"],
    "ACL tear": ["anterior-cruciate-ligament-tear", "acl-tear"],
    "Achilles tendon rupture": ["achilles-tendon-rupture"],

    # Endocrine
    "Thyroid nodule": ["thyroid-nodule"],
    "Thyroid goiter": ["goitre", "thyroid-goitre", "thyroid-goiter"],
    "Parathyroid adenoma": ["parathyroid-adenoma"],
    "Adrenal adenoma": ["adrenal-adenoma"],
    "Pheochromocytoma": ["phaeochromocytoma", "pheochromocytoma"],
    "Cushing syndrome (pituitary adenoma)": ["cushing-disease", "pituitary-adenoma"],

    # Reproductive
    "Ovarian cyst": ["ovarian-cyst"],
    "Uterine fibroids": ["uterine-fibroids", "leiomyomas"],
    "Prostate enlargement (BPH)": ["benign-prostatic-hyperplasia"],
    "Testicular torsion": ["testicular-torsion"],

    # Oncology
    "Tumor (general)": ["neoplasm", "mass"],
    "Lymphoma": ["lymphoma"],
    "Metastases": ["metastases"],
    "Breast cancer": ["breast-cancer"],
    "Pancreatic cancer": ["pancreatic-adenocarcinoma", "pancreatic-cancer"],

    # Other
    "Splenomegaly": ["splenomegaly"],
    "Splenic rupture": ["splenic-injury", "splenic-laceration"],
    "Ascites": ["ascites"],
    "Sinusitis": ["acute-sinusitis", "sinusitis"],
    "Pancreatitis": ["acute-pancreatitis", "pancreatitis"],
    "UTI/Pyelonephritis": ["pyelonephritis"],
    "Inguinal hernia": ["inguinal-hernia"],
    "Abdominal aortic calcification": ["aortic-calcification", "vascular-calcifications", "aortic-atherosclerosis"],
}

# ------------------------ session and helpers ------------------------

def make_session():
    """
    Prefer cloudscraper. Fall back to requests with retries and browser headers.
    """
    try:
        import cloudscraper
        s = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        return s
    except Exception:
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": BASE + "/",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "Upgrade-Insecure-Requests": "1",
            "DNT": "1",
            "Connection": "keep-alive",
        })
        retry = Retry(
            total=5,
            backoff_factor=0.8,
            status_forcelist=[406, 429, 500, 502, 503, 504],
            allowed_methods=frozenset(["GET"]),
        )
        s.mount("https://", HTTPAdapter(max_retries=retry))
        return s


def sleep(a=0.6, b=1.2):
    time.sleep(random.uniform(a, b))


def norm_slug(s: str) -> str:
    s = s.lower()
    s = re.sub(r"\(.*?\)", "", s)
    s = s.replace("&", "and")
    s = re.sub(r"[^a-z0-9\s-]+", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    return s


def candidate_article_slugs(condition: str):
    seeds = SEED_SLUGS.get(condition, [])
    out = list(seeds) + [norm_slug(condition)]
    seen = set()
    uniq = []
    for x in out:
        if x and x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def text_safe(node) -> str:
    if not node:
        return ""
    try:
        return node.get_text(" ", strip=True)
    except Exception:
        try:
            return node.get_text(" ")
        except Exception:
            return ""


def norm_img_url(u: str):
    if not u:
        return None
    if u.startswith("//"):
        return "https:" + u
    if u.startswith("/images/"):
        return "https://prod-images-static.radiopaedia.org" + u
    return u


def push_img(store: list, u: str):
    u = norm_img_url(u)
    if not u:
        return
    if "prod-images-static.radiopaedia.org/images" not in u:
        return
    if u not in store:
        store.append(u)


def has_case_word(text: str) -> bool:
    if not text:
        return False
    return re.search(r"\bcase\b", text, flags=re.I) is not None


def fetch(session, url: str, warm: bool = True):
    try:
        if warm:
            session.get(BASE + "/", timeout=15)
            sleep()
        r = session.get(url, timeout=30)
        if r.status_code in (406, 429):
            sleep(1.2, 2.2)
            r = session.get(url, timeout=30)
        return r
    except Exception:
        return None


# ------------------------ extraction logic ------------------------


def collect_case_caption_images(html: str, limit: int, session) -> list:
    """
    From an article HTML:
      - extract prod-images URLs directly from the page using regex
      - optionally follow case links for additional images
    """
    out = []

    # 1) Extract prod-images URLs directly from HTML using regex
    prod_pattern = r'https://prod-images-static\.radiopaedia\.org/images/[^\s"\'<>]+'
    found = re.findall(prod_pattern, html)
    for u in found:
        # Prefer _big_gallery versions for better quality
        if '_big_gallery' in u or '_gallery' in u:
            push_img(out, u)
            if len(out) >= limit:
                return out[:limit]
    
    # Add any remaining non-gallery images if we still need more
    for u in found:
        push_img(out, u)
        if len(out) >= limit:
            return out[:limit]
    
    # 2) If we still need more images, follow case links
    if len(out) < limit:
        soup = BeautifulSoup(html, "html.parser")
        case_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/cases/" in href:
                url = href if href.startswith("http") else (BASE + href)
                if url not in case_links:
                    case_links.append(url)
                if len(case_links) >= 5:  # Limit case page visits
                    break

        # Visit each case link and scrape images
        for url in case_links:
            r = fetch(session, url, warm=False)
            if r and r.status_code == 200:
                case_imgs = re.findall(prod_pattern, r.text)
                for u in case_imgs:
                    push_img(out, u)
                    if len(out) >= limit:
                        return out[:limit]
            if len(out) >= limit:
                break

    return out[:limit]

def try_articles(session, slugs, max_images):
    for slug in slugs:
        url = f"{BASE}/articles/{slug}"
        r = fetch(session, url)
        if r and r.status_code == 200:
            imgs = collect_case_caption_images(r.text, max_images, session=session)
            if imgs:
                return url, imgs
        sleep()
    return None, []


def ddg_first_rp(session, query: str):
    u = f"https://duckduckgo.com/html/?q={quote_plus('site:radiopaedia.org ' + query)}"
    r = fetch(session, u, warm=False)
    if not r or r.status_code != 200:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    best = None
    # prefer case pages
    for a in soup.select("a.result__a"):
        href = a.get("href", "")
        if "radiopaedia.org" in href and "/cases/" in href:
            return href
        if "radiopaedia.org" in href and best is None:
            best = href
    return best


def try_search(session, condition: str, max_images: int):
    for q in (condition, condition + " radiology"):
        url = ddg_first_rp(session, q)
        if not url:
            continue
        if not url.startswith("http"):
            url = "https://" + url.lstrip("/")
        r = fetch(session, url)
        if r and r.status_code == 200:
            imgs = collect_case_caption_images(r.text, max_images, session=session)
            if imgs:
                return url, imgs
        sleep()
    return None, []


# ------------------------------ main ------------------------------

def main(max_images=DEFAULT_MAX_IMAGES, out_csv=DEFAULT_OUT_CSV):
    s = make_session()
    rows = []
    for cat, items in CATEGORIES.items():
        for cond in items:
            slugs = candidate_article_slugs(cond)
            page_url, imgs = try_articles(s, slugs, max_images)
            if not imgs:
                page_url, imgs = try_search(s, cond, max_images)
            status = "ok" if imgs else "not_found"

            if imgs:
                for i, u in enumerate(imgs, start=1):
                    print(f"{cat} | {cond} -> {page_url} [{i}] {u}")
                    rows.append({
                        "category": cat,
                        "condition": cond,
                        "page_url": page_url,
                        "image_url": u,
                        "index": i,
                        "status": status
                    })
            else:
                print(f"{cat} | {cond} -> not_found")
                rows.append({
                    "category": cat,
                    "condition": cond,
                    "page_url": "",
                    "image_url": "",
                    "index": "",
                    "status": status
                })
            sleep()

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["category", "condition", "page_url", "image_url", "index", "status"])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {out_csv}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-images", type=int, default=DEFAULT_MAX_IMAGES, help="Max images per condition")
    ap.add_argument("--csv", default=DEFAULT_OUT_CSV, help="Output CSV path")
    args = ap.parse_args()
    main(max_images=args.max_images, out_csv=args.csv)
