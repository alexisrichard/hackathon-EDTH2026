# Coastal cameras — candidate feeds for AIS↔camera fusion

Companion to [`coastal_cameras.csv`](coastal_cameras.csv). This is a **data-prep catalog
only** — a shortlist of public Baltic port/coastal webcams to test vessel detection
against, cross-referenced with our AIS coverage. The detector + AIS-fusion logic is
hackathon-weekend work and is deliberately **not** built here.

## Why this exists — the "dark vessel" cue

The high-value signal for our cueing engine:

> **A camera detects a vessel where AIS shows nothing → candidate dark vessel.**

Plus two secondary signals: **corroboration** (AIS contact + camera confirms type) and
**spoofing** (AIS claims a position/type the camera contradicts). Optical cameras only
work in daylight/clear weather — the same ~70% cloud limit as Sentinel-2 — so this is a
*high-confidence, clear-weather* layer that complements SAR, not a replacement.

## How the shortlist was prioritised

1. **Colocated AIS ground truth** — a feed is only useful if we also have AIS for the
   same water. Danish bulk AIS is strong across the Belts/Sound/western+central Baltic and
   weak in the Gulf of Finland / eastern Baltic (see `DATA_GUIDE.md`). AISStream live covers
   everywhere. The `ais_coverage` column reflects this.
2. **Tight view over a defined channel** beats a wide hazy panorama — locks, straits, and
   harbour mouths give clean, countable vessel crossings.
3. **Proximity to a point of interest** — our chokepoints (`chokepoints.geojson`) and
   incident sites (`incidents.csv`). The `near_poi` column maps each cam.

**Top picks** (strong AIS + chokepoint): `CAM-STOREBAELT-E` (Great Belt) and
`CAM-HELSINGOR-PORT` (Øresund). **Best detector-dev feeds** (slow, dense, close traffic):
the Kiel Canal locks (`CAM-KIEL-HOLTENAU`, `CAM-BRUNSBUTTEL`). **Best incident tie-in**:
the Helsinki/Tallinn ferry corridor cams sit near the Balticconnector (INC-2023-10-08) and
Estlink-2 (INC-2024-12-25) sites — though Danish historical AIS is weak there, so use
AISStream live for those.

## Verification status — READ THIS

These were found by web search on **2026-06-08** and are **not yet individually confirmed
live**. Coordinates are **approximate** place-level (good to ~hundreds of m, fine for
AIS-area matching, *not* for pixel homography). Specifically:

- **Official port/bridge cam pages are JavaScript-rendered**, so the direct stream (HLS)
  URL isn't in the page source — you resolve it in-browser at dev time (below).
- **YouTube live video IDs rotate.** The IDs in the CSV may be stale; use the channel as the
  durable entry point and grab the current live ID.
- `CAM-HELSINGBORG-PORT` was **reported offline in May 2026** — verify before relying on it.

Treat the CSV as leads to confirm, not guaranteed-working endpoints.

### Confirmed working (re-validated 2026-06-08)

Three YouTube live feeds resolve + capture cleanly with yt-dlp/ffmpeg; fresh sample clips
+ frames for all three are in S3 (`s3://edth2026-baltic/cameras/`). Quality is **not**
equal — capturability ≠ fitness:

- `CAM-KIEL-HOLTENAU` — **best**, 1280×720, lots of vessels (tug + Color Line ferry +
  cargo at the lock). Note: this camera **pans / PTZ-cycles**, so the view changes over
  time → fine for detection, but **no fixed homography**.
- `CAM-BRUNSBUTTEL` — 1280×720, cargo ships in the lock (ship name "BOSNIA" legible).
  Geography is North Sea / Elbe, **not Baltic** — detector-dev only.
- `CAM-KIEL-HOLTENAU-ALT` — **weakest**, only 640×360, a cluttered shipyard panorama.

All three are **canal-lock / harbour** scenes — good for *detection* benchmarking, but a
poor environment for the *AIS dark-vessel* signal (controlled all-AIS traffic + AIS-less
small craft → false positives). For the demo narrative you still want an open-water
**chokepoint** cam (Great Belt / Øresund), which sits behind a JS player.

The operator-page feeds (livespotting Warnemünde, BalticLiveCam Tallinn) are **not**
resolvable by yt-dlp's generic extractor — grab their `.m3u8` in a browser instead.

> Re-capture footage fresh on the day — live stream IDs rotate, and the capture script now
> passes `--force-overwrites` so a re-run actually replaces the clip instead of silently
> keeping a stale one.

### Mission-useful (chokepoint) feeds — status 2026-06-08

The Kiel/Brunsbüttel feeds above are good for *detector dev* but are locks, not the
dark-vessel environment. Status of the feeds that actually fit the demo:

- **`CAM-STOREBAELT-E` / `CAM-STOREBAELT-SPROGO` (Great Belt) — ✅ CONFIRMED LIVE.** The
  player iframe (`player.sob.m-dn.net/sb1|sb2-live.html`) exposes a **stable direct HLS**:
  `https://stream.sob.m-dn.net/live/sb1/index.m3u8` (and `sb2`). No rotating ID → the most
  demo-robust feed we have. Two angles (pylon-down + low-angle), both with a burned-in
  timestamp, captured to S3. **This is the one to build the demo on.** Open-water Great Belt
  chokepoint, strong Danish AIS.
- **`CAM-HELSINKI-WEST` (Helsinki West Harbour → Tallinn ferry gateway) — ✅ CONFIRMED LIVE**
  via headless-browser screen-recording. It's an embed-locked YouTube broadcast
  (`6hPWq2IG08M`) served over SABR, so yt-dlp returns "No video formats" and there's no clean
  HLS; `resolve_stream_url.py` located it, then a Playwright recording of the rendered player
  captured it (clip+frame in S3). **Caveat:** the capture carries YouTube player overlays.
  Gulf of Finland, near Balticconnector/Estlink — Danish AIS is weak here, so pair with
  AISStream live.
- **`CAM-HELSINGOR-PORT` (Øresund) — ⛔ source cam OFFLINE today.** A headless browser passed
  Cloudflare fine, but the webcamtaxi player showed **"TEMPORARILY OFFLINE"**. Retry later, or
  swap in an alternate Øresund / Helsingborg cam.

### Resolving JS-player / Cloudflare cams headlessly

`python scripts/ingest/resolve_stream_url.py <page-url>` loads the page in headless Chromium
(Playwright) and sniffs the network for the `.m3u8` — it passes Cloudflare and runs the JS
that injects the stream, which plain yt-dlp/requests can't. Feed any URL it finds to
`capture_camera_clip.py`. If the source is an **embed-locked YouTube/SABR** stream (no
pullable HLS, like West Harbour), fall back to recording the rendered player with Playwright
(`record_video_dir`) and crop to the player box — that's how `CAM-HELSINKI-WEST` was captured.
Requires `pip install playwright && python -m playwright install chromium`.

## How to resolve a direct stream URL

For an official-site / aggregator player:
1. Open the `stream_url` in Chrome, start the player.
2. DevTools → Network → filter `m3u8` (HLS) → copy the `.m3u8` request URL.

For a YouTube live stream (most reliable to capture):
```bash
# get the current live HLS manifest for a channel's active stream
yt-dlp -g "https://www.youtube.com/watch?v=<LIVE_ID>"
```

## How to capture a sample clip (for offline detector testing)

Use the script — it bakes in the working recipe (muxed-HLS format + correctly-quoted
duration arg) so you don't re-hit the format/quoting gotchas:

```bash
python scripts/ingest/capture_camera_clip.py CAM-KIEL-HOLTENAU \
    "https://www.youtube.com/watch?v=ll6Yep9Va5o" --secs 20 --s3
```

It writes `<cam_id>_sample.mp4` + `<cam_id>_frame.jpg` to `data/reference/raw/cameras/`
(gitignored) and, with `--s3`, uploads both to `s3://edth2026-baltic/cameras/`.

Two gotchas the script handles (raw-command users beware):
- **Pick a muxed HLS format** (`-f 95/94/93` for YouTube live = 720/480/360p). Bare
  `-f best` can select separate video+audio and fail to mux.
- **Pass `ffmpeg_i:-t <secs>` as ONE argument.** If the shell splits it, `<secs>` is read
  as a second download → *"Fixed output name but more than one file to download"*.

## Terms of use — be careful (consistent with `SOURCES.md` discipline)

- **Displaying** a public webcam live is generally fine.
- **Recording / storing / redistributing** is governed by each source's ToS. Prefer the
  **official / original** source over a re-embedding aggregator (webcamtaxi, worldcam,
  skylinewebcams re-stream others' feeds — murkier rights).
- **YouTube ToS** prohibits permanent re-streaming; short clips for *internal* model
  development are low-risk, but **do not redistribute** them or bake them into a shippable
  product without checking.
- Per-source notes are in the `tos_note` column. None of these are cleared for commercial
  redistribution — flag in `SOURCES.md` if that changes.

## Suggested next steps (weekend, not now)

1. Confirm 2–3 feeds are live; resolve their HLS URLs; capture sample clips.
2. Run an off-the-shelf YOLO11 ("boat" is a COCO class) + `supervision` ByteTrack on a clip
   to sanity-check detection on these specific views.
3. MVP fusion: a `supervision` line/zone counter over the channel vs. AISStream contacts in
   that area/time → discrepancy = dark-vessel flag. (Homography-based pixel↔AIS projection
   is the stretch goal; it needs precise camera calibration and breaks easily.)
4. **De-risk the demo:** drive it from a *recorded* clip + live AISStream rather than a
   live multi-camera system on stage.

## Sources

- BalticLiveCam — https://balticlivecam.com/
- Storebælt (Great Belt) operator cams — https://storebaelt.dk/en/traffic-weather/webcams/
- Port of Kiel — https://www.portofkiel.com/webcam-en.html
- Port of Helsinki web cameras — https://portofhelsinki.fi/en/port-helsinki/web-cameras/south-harbour
- Freeport of Riga port webcams — https://rop.lv/en/port-webcams
- Helsingør port (aggregator) — https://www.webcamtaxi.com/en/denmark/capital-region-of-denmark/helsingor-port.html
- Port of Helsingborg state-of-port cam — https://www.port.helsingborg.se/en/state-of-port/
- livespotting (Rostock/Warnemünde) — https://livespotting.tv/deutschland/rostock
- Kiel Canal locks live (YouTube) — https://www.youtube.com/watch?v=ll6Yep9Va5o
- Brunsbüttel lock live (YouTube) — https://www.youtube.com/watch?v=kLNhyIv8hfw
