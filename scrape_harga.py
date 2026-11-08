#!/usr/bin/env python3
"""
scrape_harga.py — Scraper harga BBM Pertamina
Dijalankan otomatis via GitHub Actions (update_harga.yml)
Output: harga.json

Strategi:
1. Coba scrape mypertamina.id via requests + BeautifulSoup
2. Fallback: scrape via Playwright (headless Chromium) jika halaman JS-rendered
3. Fallback terakhir: pertahankan harga.json lama, jangan overwrite
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Harga hardcode sebagai fallback terakhir ──────────────────────────────────
HARGA_FALLBACK = [
    {"nama": "Pertalite",      "harga": 10000, "warna": "#22c55e", "ron": "RON 90", "tipe": "subsidi"},
    {"nama": "Pertamax",       "harga": 15950, "warna": "#f97316", "ron": "RON 92", "tipe": "nonsubsidi"},
    {"nama": "Pertamax Turbo", "harga": 19600, "warna": "#ef4444", "ron": "RON 98", "tipe": "nonsubsidi"},
    {"nama": "Dexlite",        "harga": 23700, "warna": "#3b82f6", "ron": "CN 51",  "tipe": "nonsubsidi"},
    {"nama": "Pertamina Dex",  "harga": 25200, "warna": "#8b5cf6", "ron": "CN 53",  "tipe": "nonsubsidi"},
    {"nama": "Solar",          "harga":  6800, "warna": "#eab308", "ron": "CN 48",  "tipe": "subsidi"},
]

OUTPUT_FILE = Path("harga.json")

TARGET_URLS = [
    "https://pertaminapatraniaga.com/page/harga-terbaru-bbm",
    "https://mypertamina.id/fuels-harga",
    "https://mypertamina.id/about/product-price",
]

REGION_ANCHOR = re.compile(r"DKI\s*Jakarta", re.IGNORECASE)
REGION_WINDOW = 3000

PATTERNS = [
    ("Pertalite",      r"pertalite[\s\S]{0,400}?Rp[\s.]*([\d.]+)"),
    ("Pertamax Turbo", r"pertamax\s*turbo[\s\S]{0,400}?Rp[\s.]*([\d.]+)"),
    ("Pertamax Green", r"pertamax\s*green[\s\S]{0,400}?Rp[\s.]*([\d.]+)"),
    ("Pertamax",       r"pertamax(?!\s*turbo|\s*green|\s*\(?pertashop)[\s\S]{0,400}?Rp[\s.]*([\d.]+)"),
    ("Dexlite",        r"dexlite[\s\S]{0,400}?Rp[\s.]*([\d.]+)"),
    ("Pertamina Dex",  r"pertamina\s*dex[\s\S]{0,400}?Rp[\s.]*([\d.]+)"),
    ("Solar",          r"bio\s*solar[\s\S]{0,400}?Rp[\s.]*([\d.]+)"),
]


def parse_harga(html: str) -> dict[str, int]:
    def extract(area: str) -> dict[str, int]:
        found = {}
        for nama, pattern in PATTERNS:
            m = re.search(pattern, area, re.IGNORECASE)
            if m:
                h = int(m.group(1).replace(".", ""), 10)
                if 1000 < h < 100_000:
                    found[nama] = h
        return found

    anchor = REGION_ANCHOR.search(html)
    result = {}
    if anchor:
        section = html[anchor.start(): anchor.start() + REGION_WINDOW]
        result = extract(section)

    if len(result) < 3:
        fallback = extract(html)
        for nama, harga in fallback.items():
            result.setdefault(nama, harga)

    return result


def scrape_requests() -> dict[str, int] | None:
    import requests
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Mobile Safari/537.36"
        ),
        "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    }
    for url in TARGET_URLS:
        try:
            r = requests.get(url, headers=headers, timeout=20)
            r.raise_for_status()
            found = parse_harga(r.text)
            if len(found) >= 3:
                print(f"[requests] Berhasil dari {url}: {found}")
                return found
            print(f"[requests] {url} hanya menemukan {len(found)} harga")
        except Exception as e:
            print(f"[requests] {url} error: {e}")
    return None


def scrape_playwright() -> dict[str, int] | None:
    from playwright.sync_api import sync_playwright
    for url in TARGET_URLS:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(
                    user_agent=(
                        "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0 Mobile Safari/537.36"
                    )
                )
                page.goto(url, wait_until="networkidle", timeout=30_000)
                html = page.content()
                browser.close()
            found = parse_harga(html)
            if len(found) >= 3:
                print(f"[playwright] Berhasil dari {url}: {found}")
                return found
            print(f"[playwright] {url} hanya menemukan {len(found)} harga")
        except Exception as e:
            print(f"[playwright] {url} error: {e}")
    return None


def load_existing() -> list[dict] | None:
    if OUTPUT_FILE.exists():
        try:
            d = json.loads(OUTPUT_FILE.read_text())
            return d.get("bbm")
        except Exception:
            pass
    return None


def build_output(scraped: dict[str, int] | None, base: list[dict]) -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    bbm   = []
    for item in base:
        entry = dict(item)
        if scraped and item["nama"] in scraped:
            entry["harga"] = scraped[item["nama"]]
        bbm.append(entry)
    return {
        "updated": today,
        "source":  "scraped" if scraped else "fallback",
        "note":    "Harga untuk wilayah DKI Jakarta & Jabodetabek (PBBKB 5%). Harga di luar Jawa dapat berbeda.",
        "bbm":     bbm,
    }


def main():
    print(f"=== scrape_harga.py | {datetime.now().strftime('%Y-%m-%d %H:%M')} ===")

    scraped = scrape_requests() or scrape_playwright()
    base = load_existing() or HARGA_FALLBACK
    output = build_output(scraped, base)
    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"harga.json ditulis: {output['source']} | {output['updated']}")

    if not scraped:
        print("⚠️  Scraping gagal — menggunakan data cache/fallback", file=sys.stderr)


if __name__ == "__main__":
    main()
