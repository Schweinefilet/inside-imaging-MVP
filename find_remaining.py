#!/usr/bin/env python3
"""
Try to find images for the 36 remaining conditions using more aggressive strategies
"""
import cloudscraper
import re
import time
import random
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

BASE = "https://radiopaedia.org"

# The 36 conditions that didn't have images
REMAINING = [
    "ARDS", "Abdominal aortic calcification", "Achilles tendon rupture",
    "Ankylosing spondylitis", "Appendicitis", "Biliary obstruction",
    "Brain tumor", "Breast cancer", "Budd-Chiari syndrome",
    "Cervical spondylosis", "Chiari malformation", "Colon cancer",
    "Crohn's disease", "Diverticulitis", "Emphysema",
    "Epidural hematoma", "Esophageal cancer", "Fatty liver",
    "Fractures (general)", "Gallstones", "Gastric cancer",
    "Liver cyst", "Liver metastases", "Metastases",
    "Ovarian cyst", "Pheochromocytoma", "Pulmonary fibrosis",
    "Renal cell carcinoma", "Sinusitis", "Spinal stenosis",
    "Splenic rupture", "Subdural hematoma", "Thyroid goiter",
    "Tumor (general)", "Uterine fibroids", "Vertebral compression fracture"
]

def make_session():
    return cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )

def sleep_random():
    time.sleep(random.uniform(0.8, 1.5))

def fetch_page(session, url):
    try:
        r = session.get(url, timeout=30)
        if r.status_code == 200:
            return r.text
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
    return None

def extract_prod_images(html):
    """Extract prod-images-static.radiopaedia.org URLs from HTML"""
    if not html:
        return []
    pattern = r'https://prod-images-static\.radiopaedia\.org/images/[^\s"\'<>]+'
    found = re.findall(pattern, html)
    # Prefer gallery versions
    unique = []
    for url in found:
        if url not in unique:
            unique.append(url)
    return unique

def try_direct_search(session, condition):
    """Try searching Radiopaedia directly"""
    search_url = f"{BASE}/search?lang=us&q={quote_plus(condition)}"
    print(f"  Trying direct search: {search_url}")
    html = fetch_page(session, search_url)
    if html:
        # Look for article links
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/articles/' in href and BASE not in href:
                article_url = BASE + href
                print(f"    Found article: {article_url}")
                article_html = fetch_page(session, article_url)
                imgs = extract_prod_images(article_html)
                if imgs:
                    return article_url, imgs[:3]
                sleep_random()
    return None, []

def try_case_search(session, condition):
    """Try finding case pages directly"""
    search_url = f"{BASE}/cases?lang=us&q={quote_plus(condition)}"
    print(f"  Trying case search: {search_url}")
    html = fetch_page(session, search_url)
    if html:
        soup = BeautifulSoup(html, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/cases/' in href and BASE not in href:
                case_url = BASE + href
                print(f"    Found case: {case_url}")
                case_html = fetch_page(session, case_url)
                imgs = extract_prod_images(case_html)
                if imgs:
                    return case_url, imgs[:3]
                sleep_random()
                break  # Only try first case
    return None, []

def main():
    session = make_session()
    results = {}
    
    for condition in REMAINING:
        print(f"\n{'='*60}")
        print(f"Searching: {condition}")
        print(f"{'='*60}")
        
        # Try direct article search first
        url, imgs = try_direct_search(session, condition)
        if not imgs:
            # Try case search
            url, imgs = try_case_search(session, condition)
        
        if imgs:
            results[condition] = {"url": url, "images": imgs}
            print(f"  ✅ Found {len(imgs)} images")
            for i, img in enumerate(imgs, 1):
                print(f"    {i}. {img[:80]}...")
        else:
            print(f"  ❌ No images found")
        
        sleep_random()
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"✅ Found: {len(results)}/{len(REMAINING)}")
    print(f"❌ Still missing: {len(REMAINING) - len(results)}")
    
    # Save results
    import json
    with open('remaining_conditions.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n📝 Saved to remaining_conditions.json")

if __name__ == "__main__":
    main()
