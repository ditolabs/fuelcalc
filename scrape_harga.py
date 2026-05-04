#!/usr/bin/env python3
"""
scrape_harga.py
Scraper harga BBM Pertamina untuk BBM Tracker PWA.
Mencoba beberapa sumber secara berurutan (fallback chain).

Sumber:
  1. pertaminapatraniaga.com  — sumber resmi (via Playwright headless)
  2. mypertamina.id/fuels-harga — fallback resmi
  3. Liputan6 / Kompas         — fallback berita
  4. Hardcode terakhir         — jika semua gagal
"""

import json, re, sys, datetime, os
from pathlib import Path

# ── Harga fallback terakhir (diupdate manual jika diperlukan) ──
FALLBACK = {
    "updated": "2026-05-04",
    "source": "fallback",
    "wilayah": "Jawa-Bali",
    "bbm": [
        {"nama": "Pertalite",       "harga": 10000, "warna": "#22c55e"},
        {"nama": "Pertamax",        "harga": 12300, "warna": "#f97316"},
        {"nama": "Pertamax Turbo",  "harga": 19900, "warna": "#ef4444"},
        {"nama": "Dexlite",         "harga": 26000, "warna": "#3b82f6"},
        {"nama": "Pertamina Dex",   "harga": 27900, "warna": "#8b5cf6"},
    ]
}

OUTPUT_FILE = Path(__file__).parent / "harga.json"


def log(msg):
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}")


def parse_price(text):
    """Ekstrak angka harga dari teks, return int atau None."""
    text = str(text).replace(".", "").replace(",", "").strip()
    m = re.search(r"\b(\d{4,6})\b", text)
    if m:
        val = int(m.group(1))
        if 5000 <= val <= 50000:
            return val
    return None


def load_existing():
    """Load harga.json yang sudah ada sebagai base."""
    if OUTPUT_FILE.exists():
        try:
            return json.loads(OUTPUT_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return FALLBACK.copy()


# ══════════════════════════════════════
#  SUMBER 1: pertaminapatraniaga.com
#  (Playwright headless Chrome)
# ══════════════════════════════════════
def scrape_ppatraniaga():
    log("Mencoba pertaminapatraniaga.com (Playwright)...")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ))
            page.goto(
                "https://pertaminapatraniaga.com/page/harga-terbaru-bbm",
                wait_until="networkidle",
                timeout=30000
            )
            content = page.content()
            browser.close()

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(content, "lxml")

        # Mapping nama produk
        targets = {
            "pertalite":       ("Pertalite",       "#22c55e"),
            "pertamax turbo":  ("Pertamax Turbo",  "#ef4444"),
            "pertamax":        ("Pertamax",        "#f97316"),
            "dexlite":         ("Dexlite",         "#3b82f6"),
            "pertamina dex":   ("Pertamina Dex",   "#8b5cf6"),
        }
        hasil = {}

        # Cari tabel atau div yang berisi harga
        for el in soup.find_all(["td", "th", "div", "span", "p", "li"]):
            teks = el.get_text(" ", strip=True).lower()
            for key, (nama, warna) in targets.items():
                if key in teks and nama not in hasil:
                    # Coba ambil harga dari sibling atau parent
                    parent = el.find_parent(["tr", "div", "li"])
                    if parent:
                        teks_parent = parent.get_text(" ", strip=True)
                        harga = parse_price(teks_parent)
                        if harga:
                            hasil[nama] = {"nama": nama, "harga": harga, "warna": warna}

        if len(hasil) >= 3:
            log(f"  ✅ Berhasil: {len(hasil)} produk ditemukan")
            return list(hasil.values())

        log(f"  ⚠️  Hanya {len(hasil)} produk — data kurang lengkap")
        return None

    except Exception as e:
        log(f"  ❌ Gagal: {e}")
        return None


# ══════════════════════════════════════
#  SUMBER 2: mypertamina.id
# ══════════════════════════════════════
def scrape_mypertamina():
    log("Mencoba mypertamina.id...")
    try:
        import requests
        r = requests.get(
            "https://mypertamina.id/fuels-harga",
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "id"},
            timeout=15
        )
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "lxml")
        text = soup.get_text(" ")

        targets = {
            "pertalite":      ("Pertalite",      "#22c55e"),
            "pertamax turbo": ("Pertamax Turbo", "#ef4444"),
            "pertamax":       ("Pertamax",       "#f97316"),
            "dexlite":        ("Dexlite",        "#3b82f6"),
            "pertamina dex":  ("Pertamina Dex",  "#8b5cf6"),
        }
        hasil = {}

        # Cari pola: nama produk diikuti harga dalam 100 karakter
        for key, (nama, warna) in targets.items():
            pattern = re.compile(
                re.escape(key) + r".{0,100}?Rp[\s\.]*([\d\.]+)',",
                re.IGNORECASE
            )
            m = pattern.search(text)
            if not m:
                # Coba pola lebih longgar
                idx = text.lower().find(key)
                if idx > 0:
                    snippet = text[idx:idx+150]
                    harga = parse_price(snippet)
                    if harga:
                        hasil[nama] = {"nama": nama, "harga": harga, "warna": warna}
            else:
                harga = parse_price(m.group(1))
                if harga:
                    hasil[nama] = {"nama": nama, "harga": harga, "warna": warna}

        if len(hasil) >= 3:
            log(f"  ✅ Berhasil: {len(hasil)} produk")
            return list(hasil.values())

        log(f"  ⚠️  Hanya {len(hasil)} produk")
        return None

    except Exception as e:
        log(f"  ❌ Gagal: {e}")
        return None


# ══════════════════════════════════════
#  SUMBER 3: Scrape berita Liputan6
# ══════════════════════════════════════
def scrape_berita():
    log("Mencoba scrape berita harga BBM terbaru...")
    try:
        import requests
        from bs4 import BeautifulSoup

        urls = [
            "https://www.liputan6.com/tag/harga-bbm",
            "https://money.kompas.com/tag/harga+bbm",
        ]

        for url in urls:
            try:
                r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                soup = BeautifulSoup(r.text, "lxml")

                # Cari artikel terbaru tentang harga BBM
                links = []
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    title = a.get_text(strip=True).lower()
                    if "harga" in title and "bbm" in title and len(href) > 30:
                        links.append(href)
                    if len(links) >= 3:
                        break

                for link in links[:2]:
                    try:
                        r2 = requests.get(link, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
                        text = BeautifulSoup(r2.text, "lxml").get_text(" ")

                        # Extract prices from article text
                        hasil = {}
                        patterns = [
                            (r"[Pp]ertalite\s*[:\-–]?\s*Rp\s*[\.\s]*([\d\.]+)", "Pertalite", "#22c55e"),
                            (r"[Pp]ertamax [Tt]urbo\s*[:\-–]?\s*Rp\s*[\.\s]*([\d\.]+)", "Pertamax Turbo", "#ef4444"),
                            (r"[Pp]ertamax\b\s*[:\-–]?\s*Rp\s*[\.\s]*([\d\.]+)", "Pertamax", "#f97316"),
                            (r"[Dd]exlite\s*[:\-–]?\s*Rp\s*[\.\s]*([\d\.]+)", "Dexlite", "#3b82f6"),
                            (r"[Pp]ertamina [Dd]ex\s*[:\-–]?\s*Rp\s*[\.\s]*([\d\.]+)", "Pertamina Dex", "#8b5cf6"),
                        ]
                        for patt, nama, warna in patterns:
                            m = re.search(patt, text)
                            if m:
                                harga = parse_price(m.group(1))
                                if harga:
                                    hasil[nama] = {"nama": nama, "harga": harga, "warna": warna}

                        if len(hasil) >= 3:
                            log(f"  ✅ Dari berita: {len(hasil)} produk ({link[:60]})")
                            return list(hasil.values())
                    except Exception:
                        continue
            except Exception:
                continue

        return None
    except Exception as e:
        log(f"  ❌ Gagal: {e}")
        return None


# ══════════════════════════════════════
#  MAIN
# ══════════════════════════════════════
def main():
    log("=" * 50)
    log("BBM Tracker — Scraper Harga Pertamina")
    log("=" * 50)

    existing = load_existing()
    bbm_data = None

    # Coba sumber berurutan
    for scraper in [scrape_ppatraniaga, scrape_mypertamina, scrape_berita]:
        bbm_data = scraper()
        if bbm_data and len(bbm_data) >= 3:
            break

    if not bbm_data:
        log("⚠️  Semua sumber gagal — menggunakan data terakhir tersimpan")
        # Pertahankan data yang sudah ada, hanya update timestamp jika source fallback
        if existing.get("source") != "fallback":
            log(f"✅ Data tersimpan masih valid (terakhir: {existing.get('updated')})")
            sys.exit(0)  # Tidak ada perubahan
        bbm_data = FALLBACK["bbm"]
        source = "fallback"
    else:
        source = "scraped"

    # Pastikan semua 5 produk ada (merge dengan existing jika ada yang hilang)
    nama_existing = {b["nama"]: b for b in existing.get("bbm", [])}
    nama_baru = {b["nama"]: b for b in bbm_data}

    # Gabungkan: prioritas data baru, fallback ke existing
    final_bbm = []
    urutan = ["Pertalite", "Pertamax", "Pertamax Turbo", "Dexlite", "Pertamina Dex"]
    warna_map = {
        "Pertalite": "#22c55e", "Pertamax": "#f97316",
        "Pertamax Turbo": "#ef4444", "Dexlite": "#3b82f6",
        "Pertamina Dex": "#8b5cf6"
    }
    for nama in urutan:
        if nama in nama_baru:
            final_bbm.append(nama_baru[nama])
        elif nama in nama_existing:
            log(f"  ⚠️  {nama} tidak ditemukan di sumber baru, pakai data lama")
            final_bbm.append(nama_existing[nama])
        else:
            # Cari dari FALLBACK
            fb = next((b for b in FALLBACK["bbm"] if b["nama"] == nama), None)
            if fb:
                final_bbm.append(fb)

    today = datetime.date.today().strftime("%Y-%m-%d")
    result = {
        "updated": today,
        "source": source,
        "wilayah": "Jawa-Bali",
        "bbm": final_bbm
    }

    # Cek apakah ada perubahan harga
    old_prices = {b["nama"]: b["harga"] for b in existing.get("bbm", [])}
    new_prices = {b["nama"]: b["harga"] for b in final_bbm}
    changes = {k: (old_prices.get(k), v) for k, v in new_prices.items() if old_prices.get(k) != v}

    if changes:
        log("📊 Perubahan harga terdeteksi:")
        for nama, (lama, baru) in changes.items():
            delta = baru - (lama or 0)
            log(f"  {nama}: Rp {lama:,} → Rp {baru:,} ({'+' if delta > 0 else ''}{delta:,})")
    else:
        log("ℹ️  Tidak ada perubahan harga")

    OUTPUT_FILE.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    log(f"✅ harga.json disimpan ({today})")
    log("=" * 50)


if __name__ == "__main__":
    main()
