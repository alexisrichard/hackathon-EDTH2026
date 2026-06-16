# HEIMDALL.ai — pitch deck (HTML → PDF)

A self-contained, brand-styled HTML presentation. Backdrops for a speaker (minimal text); the words live in [`../PITCH.md`](../PITCH.md). 17 slides, 16:9.

## Present
```bash
# served by the 'deck-preview' launch config (python http.server on :8950)
# or any static server:
python -m http.server 8950 --directory outreach/deck
# open http://localhost:8950
```
- **← / → / space** navigate · **F** fullscreen · **Home/End** jump · deep-link with `#<n>`.
- Built to the **locked brand system** in `brand/heimdall_brand_identity.html` (Doc 03): `HEIMDALL.AI` wordmark (Space Grotesk + JetBrains Mono, `.AI` muted), **R5 "Apex Cue"** mark, Bifröst Cyan `#41E3FF`, the suspicion bands + **sensor colors** (SAR cue surfaces = `--sensor-sar #7AA2F7`, not cyan), dark vessels as hollow Breach-Red glyphs. Token block + R5 geometry copy-pasted from the guide's §13.

## Export to PDF
**Easiest:** click **SAVE PDF** (top-right) → Chrome print dialog → *Save as PDF*, **Landscape**, **Margins: None**, **Background graphics: ON**. One slide per page.

**Reproducible (headless):**
```bash
python outreach/deck/export_pdf.py            # → outreach/deck/HEIMDALL_deck.pdf
```
(Needs the deck server running. Uses the venv's Playwright Chromium; honours the `@page` size + backgrounds.)

## Drop-in assets (`assets/`)
The deck renders fully without these (graceful dashed placeholders), but they make it land:

| File | Slide | What |
|---|---|---|
| `sar_clion1.jpg` ✅ | 9 (SAR) + 1 (title bg) | Real Sentinel-1 scene, C-Lion1 area. *Already pulled from S3.* |
| `sar_nordstream.jpg` ✅ | spare | Real Sentinel-1 scene, Nord Stream. *Already pulled from S3.* |
| **`model_before.png`** | **10** | Base-YOLOv8n panel (few/no detections) from `scripts/eval/compare_before_after_finetuning.py`. |
| **`model_after.png`** | **10** | Fine-tuned panel (locks every hull) — same script. |
| `app_clion1.png` | 14 (demo) | Screenshot / first video frame of the C-Lion1 replay (the `#1 · SAR · 0.88` cue on the map). |

**Model before/after (the one we must nail):** drop the two panels as `model_before.png` / `model_after.png`. If you only have the single combined matplotlib export, drop it in and tell me — I'll split/restyle it, or regenerate a clean branded pair (the fine-tuned weights are on S3 at `scoring/weights/yolov8n_hrsid_best.pt`).

## Slides
1 Title · 2 The crime · 3 Stakes (99%) · 4 Nine cuts · 5 Prioritization · 6 Ships lie ·
7 Three senses · 8 Scoring · 9 SAR vision · **10 Model before/after** · 11 Geography ·
12 Alone, blind · 13 The gap (money slide) · 14 Demo · 15 Verdict · 16 Why now/wedge · 17 Close.
