"""Export the Heimdall HTML deck to a print-ready PDF (one slide per landscape page).

Prereq: the deck server running (preview 'deck-preview' on :8950) OR pass a URL.
Usage:  python outreach/deck/export_pdf.py [URL] [OUT.pdf]
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8950/"
OUT = Path(sys.argv[2] if len(sys.argv) > 2 else "outreach/deck/HEIMDALL_deck.pdf")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(URL, wait_until="networkidle")
    page.emulate_media(media="print")
    page.pdf(
        path=str(OUT),
        prefer_css_page_size=True,   # honour @page { size: 13.333in 7.5in }
        print_background=True,        # keep the dark ops-console backgrounds
    )
    browser.close()

print(f"wrote {OUT.resolve()}  ({OUT.stat().st_size // 1024} KB)")
