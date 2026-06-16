"""Capture the live Heimdall app (C-Lion1 / Yi Peng 3 hero frame) for deck slide 14.

Drives the running dev server (heimdall-ui :5173) to the default paused cue moment,
fits the map to the #1 SAR cue box, and screenshots → assets/app_clion1.png.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

URL = "http://localhost:5173/"
OUT = Path("/Users/alexisrichard/Documents/Projects/EDTH 2026/outreach/deck/assets/app_clion1.png")
GL_ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]

def run(launch):
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport={"width": 1600, "height": 900}, device_scale_factor=2)
        page.goto(URL, wait_until="networkidle")
        page.wait_for_selector(".cue-item", timeout=25000)   # scenario loaded + cues populated
        page.wait_for_timeout(3500)                            # basemap + AIS tiles settle
        btn = page.query_selector(".cue-item .btn.primary")    # "Task SAR" on #1 → fit to cue box
        if btn:
            btn.click()
            page.wait_for_timeout(2800)                         # fitBounds ease + tile load
        page.screenshot(path=str(OUT))
        # sanity: report the on-screen state
        t = page.eval_on_selector(".scrub-time", "el => el.textContent.trim()")
        sc = page.eval_on_selector(".cue-item .sc", "el => el.textContent.trim()")
        browser.close()
        return t, sc

OUT.parent.mkdir(parents=True, exist_ok=True)
try:
    t, sc = run(lambda p: p.chromium.launch(channel="chrome", headless=True, args=GL_ARGS))
    print("captured via system Chrome")
except Exception as e:
    print("chrome channel failed, falling back to bundled chromium:", str(e)[:120])
    t, sc = run(lambda p: p.chromium.launch(headless=True, args=GL_ARGS))

print(f"wrote {OUT}  ({OUT.stat().st_size//1024} KB)  | clock={t} cue#1={sc}")
