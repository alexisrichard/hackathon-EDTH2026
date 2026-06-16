"""Compose a README hero: 2x2 montage of the deck's strongest slides.
Screenshots slides 1 (title), 10 (model 0->105), 13 (the gap), 14 (the app)
from the running deck-preview server → assets/readme_hero.png
"""
from pathlib import Path
from PIL import Image, ImageOps
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8950/"
SLIDES = [1, 13, 10, 14]                       # title · gap · model · app
ASSETS = Path("/Users/alexisrichard/Documents/Projects/EDTH 2026/outreach/deck/assets")
W, H = 1280, 720
VOID = (6, 10, 18); LINE = (28, 39, 64)
GAP, MARGIN = 20, 20

def shoot(launch):
    shots = []
    with sync_playwright() as pw:
        b = launch(pw)
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=2)
        pg.goto(BASE, wait_until="networkidle")
        for n in SLIDES:
            pg.evaluate(f"show({n - 1})")      # switch slide (hash alone doesn't reload)
            pg.wait_for_timeout(1500)          # fonts + slide images settle
            p = ASSETS / f"_hero_{n}.png"
            pg.screenshot(path=str(p))
            shots.append(p)
        b.close()
    return shots

try:
    shots = shoot(lambda pw: pw.chromium.launch(channel="chrome", headless=True))
except Exception as e:
    print("chrome failed, bundled chromium:", str(e)[:100])
    shots = shoot(lambda pw: pw.chromium.launch(headless=True))

# compose 2x2
tiles = [ImageOps.expand(Image.open(p).convert("RGB").resize((W, H)), border=1, fill=LINE) for p in shots]
tw, th = tiles[0].size
canvas = Image.new("RGB", (MARGIN*2 + tw*2 + GAP, MARGIN*2 + th*2 + GAP), VOID)
for i, t in enumerate(tiles):
    x = MARGIN + (i % 2) * (tw + GAP)
    y = MARGIN + (i // 2) * (th + GAP)
    canvas.paste(t, (x, y))
out = ASSETS / "readme_hero.png"
canvas.save(out)
for p in shots:
    p.unlink(missing_ok=True)
print(f"wrote {out}  ({out.stat().st_size//1024} KB, {canvas.size[0]}x{canvas.size[1]})")
