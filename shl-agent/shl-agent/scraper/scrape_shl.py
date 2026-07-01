"""
Scrapes the SHL Product Catalog (Individual Test Solutions only) into catalog.json.

Run locally:
    pip install requests beautifulsoup4
    python scrape_shl.py

Output: ../data/catalog.json
    [
      {
        "name": "...",
        "url": "https://www.shl.com/...",
        "test_type": "K" | "P" | "A" | "B" | "C" | "D" | "E" | ... (SHL's letter codes),
        "remote_testing": true/false,
        "adaptive_irt": true/false,
        "description": "...",
        "duration_minutes": 30,
        "job_levels": ["Mid-Professional", ...]
      },
      ...
    ]

NOTE ON SITE STRUCTURE:
SHL's catalog is paginated and split into two tables on the page:
  - "Individual Test Solutions" (type=1)
  - "Pre-packaged Job Solutions"  (type=2)
We only want type=1. The site uses query params like:
  https://www.shl.com/solutions/products/product-catalog/?start=0&type=1
and paginates in increments of 12 (adjust PAGE_SIZE / MAX_PAGES if the site
has changed by the time you run this -- inspect the page and update
the CSS selectors below if scraping breaks).
"""

import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = "https://www.shl.com/solutions/products/product-catalog/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SHL-Catalog-Scraper/1.0)"}
PAGE_SIZE = 12
MAX_PAGES = 50  # safety cap; loop breaks early when a page returns no rows

OUT_PATH = Path(__file__).parent.parent / "data" / "catalog.json"


def parse_listing_page(html: str):
    """Parse one catalog listing page -> list of (name, url, test_type_letters, remote, adaptive)."""
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    # The catalog table rows live under a table whose header includes "Individual Test Solutions"
    # We target rows generically: each row has a link (name+url) and small badge cells for
    # Remote Testing / Adaptive / IRT and a "Test Type" column showing letter codes.
    for table in soup.select("table"):
        header_text = table.get_text(" ", strip=True).lower()
        if "individual test solutions" not in header_text and "test type" not in header_text:
            continue
        for tr in table.select("tr"):
            link = tr.select_one("a[href*='/product-catalog/']") or tr.select_one("a[href*='view/']")
            if not link:
                continue
            name = link.get_text(strip=True)
            url = link.get("href", "")
            if url.startswith("/"):
                url = "https://www.shl.com" + url
            # remote testing / adaptive markers are usually little green dot icons / spans
            cells = tr.select("td")
            remote = any("yes" in c.get("class", []) or "circle -yes" in " ".join(c.get("class", []))
                         for c in cells)
            # Test type letters usually appear as a string of single-letter badges in last column
            type_letters = ""
            if cells:
                last_cell_text = cells[-1].get_text(strip=True)
                letters = re.findall(r"\b[A-Z]\b", last_cell_text)
                type_letters = "".join(letters)
            rows.append({
                "name": name,
                "url": url,
                "test_type": type_letters,
                "remote_testing": remote,
            })
    return rows


def fetch_detail(url: str):
    """Fetch a single assessment's detail page for description/duration/job level."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"  ! failed to fetch detail {url}: {e}")
        return {}
    soup = BeautifulSoup(r.text, "html.parser")
    text = soup.get_text(" ", strip=True)

    desc_tag = soup.select_one(".product-catalogue-training-calendar__description, .description, article p")
    description = desc_tag.get_text(" ", strip=True) if desc_tag else ""

    duration_match = re.search(r"(\d+)\s*minutes", text, re.I)
    duration = int(duration_match.group(1)) if duration_match else None

    job_levels = []
    jl_match = re.search(r"Job Levels?:?\s*([A-Za-z,\-\s]+?)(?:Languages|Assessment length|$)", text)
    if jl_match:
        job_levels = [j.strip() for j in jl_match.group(1).split(",") if j.strip()]

    return {
        "description": description[:800],
        "duration_minutes": duration,
        "job_levels": job_levels,
    }


def scrape():
    all_rows = {}
    for start in range(0, PAGE_SIZE * MAX_PAGES, PAGE_SIZE):
        url = f"{BASE}?start={start}&type=1"
        print(f"Fetching listing: {url}")
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
        except Exception as e:
            print(f"  ! stopping, fetch failed: {e}")
            break
        rows = parse_listing_page(r.text)
        if not rows:
            print("  no more rows, stopping pagination")
            break
        new_count = 0
        for row in rows:
            if row["url"] not in all_rows:
                all_rows[row["url"]] = row
                new_count += 1
        if new_count == 0:
            print("  no new items on this page, stopping (avoid infinite loop)")
            break
        time.sleep(0.5)  # be polite

    print(f"Found {len(all_rows)} unique Individual Test Solutions. Fetching detail pages...")

    catalog = []
    for i, (url, row) in enumerate(all_rows.items(), 1):
        print(f"  [{i}/{len(all_rows)}] {row['name']}")
        detail = fetch_detail(url)
        row.update(detail)
        catalog.append(row)
        time.sleep(0.3)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(catalog, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(catalog)} items to {OUT_PATH}")


if __name__ == "__main__":
    scrape()
