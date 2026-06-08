"""Resolve the HLS (.m3u8) URL behind a JS-player / Cloudflare-protected webcam page.

Plain HTTP clients (yt-dlp, requests) get blocked by Cloudflare or never see the
stream because it's injected by JavaScript. This loads the page in a real headless
Chromium (Playwright), lets the player run, and sniffs the network for .m3u8 requests
— then you feed the manifest to capture_camera_clip.py.

Requires: pip install playwright && python -m playwright install chromium

Usage:
  python scripts/ingest/resolve_stream_url.py "https://www.skylinewebcams.com/.../port.html"
"""
import sys
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
PLAY_SELECTORS = ["video", ".vjs-big-play-button", "button[aria-label*=play i]",
                  ".play-button", ".play", "#player", ".jwplayer"]


def resolve(url: str, wait_s: int = 25) -> list[str]:
    found: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--autoplay-policy=no-user-gesture-required"],
        )
        ctx = browser.new_context(user_agent=UA, viewport={"width": 1280, "height": 800}, locale="en-US")
        ctx.add_init_script("Object.defineProperty(navigator,'webdriver',{get:()=>undefined})")
        page = ctx.new_page()

        def on_req(req):
            u = req.url
            if ".m3u8" in u.lower() and u not in found:
                found.append(u)

        page.on("request", on_req)
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=35000)
        except Exception as e:
            print(f"  goto warning: {e}")

        # nudge playback, then wait for the stream request to fire
        for _ in range(wait_s):
            if found:
                break
            for sel in PLAY_SELECTORS:
                try:
                    el = page.query_selector(sel)
                    if el:
                        el.click(timeout=800)
                except Exception:
                    pass
            page.wait_for_timeout(1000)
        page.wait_for_timeout(1500)
        browser.close()
    # de-dup, prefer master playlists
    uniq = list(dict.fromkeys(found))
    uniq.sort(key=lambda u: (0 if any(k in u.lower() for k in ("master", "index", "playlist")) else 1, len(u)))
    return uniq


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    for url in sys.argv[1:]:
        print(f"==== {url}")
        try:
            m = resolve(url)
        except Exception as e:
            print(f"  FAILED: {e}")
            continue
        print(f"  m3u8 found: {m or '- none -'}")
