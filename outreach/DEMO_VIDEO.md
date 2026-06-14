# HEIMDALL — Backup Demo Video: shot list & capture plan

> **Purpose.** A scripted, no-fail recording of the C-Lion1 / Yi Peng 3 replay (with an optional Nord Stream tag) for **slide 12** of the pitch ([PITCH.md](PITCH.md)). It does double duty: (1) the **backup** the speaker cuts to if the live app stalls >3s, and (2) the **source** for the in-deck screenshots (slides 4, 7, 8, 9, 11, 13).
>
> Everything here is verified against the running app (`heimdall-ui`, Vite @ `localhost:5173`) on 2026-06-14 — controls, timings, and on-screen numbers are real.

---

## 0. Specs

| | |
|---|---|
| **Primary cut** | **~75s**, silent, captioned — the speaker narrates live over it (no competing audio). Timed to the §4 run-sheet in PITCH.md. |
| **Also export** | **45s short** (C-Lion1 only, for a tight 3-min pitch) · **15s social teaser** (LinkedIn/judges) · **75s + voice-over** version for async sharing. |
| **Resolution** | **1920×1080, 30 fps** (60 fps if your recorder handles the map pans smoothly). Retina/2× backing store → crisp text. |
| **Format** | H.264 MP4. Also keep the raw ProRes/lossless master for re-cuts. Embed it in the deck **and** keep a local copy + a phone copy (don't rely on venue WiFi or an embed). |
| **Aesthetic** | Matches the deck: dark ops-console. Let the app's own red = "threat" carry. |

---

## 1. Pre-flight (do this before every take)

1. **Clean browser.** Chrome in a fresh window, **100% zoom**, no bookmarks bar, no extensions toolbar. Best: launch app-mode so there's no address bar —
   `open -na "Google Chrome" --args --app=http://localhost:5173 --window-size=1920,1080`
2. **Server up.** `heimdall-ui` running (`npm run dev --prefix frontend`). For max smoothness record against a production build: `npm --prefix frontend run build && npm --prefix frontend run preview` (port 4173 — update the app-mode URL).
3. **Canonical start state.** **Reload the page.** It opens **paused** at `DEFAULT_T = 2024-11-18 08:41:00Z` on the C-Lion1 / Yi Peng 3 moment. Confirm the top bar reads `2024-11-18 08:41:00Z` and the cue panel header reads `C-Lion1 / Yi Peng 3 · cued as-of 2024-11-18 08:41Z`. If it drifted (a reused session can be mid-play in 2022), reload again.
4. **Layer panel.** Leave it as default (Pipelines, Submarine cables, all vessel classes on). *Optional cleaner map:* collapse it with **DEFAULT VIEW** off-screen — but the default is fine and shows the infra toggles, which reads as "real tool."
5. **Cursor.** Hide it when idle if your recorder supports it (Kap/ScreenFlow). Never let it hover dev tooltips. Move deliberately — slow pans read better than fast jerks.
6. **Recorder.** Kap, ScreenFlow, or OBS, cropped to the 1920×1080 viewport. Do a 5s throwaway take to check text sharpness and frame rate first.

**Controls cheat-sheet (verified):**
- Play/pause = the ▶/❚❚ button. Speed cycles `60→600→3600→21600→86400×` (default 600×).
- Frame step **±30s** = `←`/`→` (or ◀/▶); **±1h** = `Shift+←`/`Shift+→` (or ◀◀/▶▶). Stepping **pauses** automatically.
- Drag the scrubber track to seek; red ticks = incidents (Nord Stream · Balticconnector · C-Lion1/Yi Peng 3 · Estlink2/Eagle S · LV–SE).
- **TASK SAR** on a cue → the map fits to that cue's box (~1.2s ease). A vessel/driver click → flyTo zoom 8.2.
- Top-bar suspicion dot goes **red at ≥0.9**.

---

## 2. Master shot list — primary 75s cut

Timecodes are cumulative. **CAP** = grab a still here for the deck. Captions are short on-screen lower-thirds; the speaker says the §4 lines live.

| # | t (s) | On screen — exact actions | Caption (lower-third) | Notes / CAP |
|---|---|---|---|---|
| 1 | 0–6 | **Hold** the canonical start, but first **scrub back ~6h**: `Shift+←` ×6 to ~02:00Z so no cue is showing yet — just real AIS tracks + cables over the Baltic. Press **play at 600×**. | `Baltic Sea · 18 Nov 2024 · real AIS` | Establishes "this is real traffic, nothing flagged yet." **CAP 4** (wide swarm) — but for the *swarm* slide, zoom out one notch first (see §3). |
| 2 | 6–14 | Let it **play forward** toward 08:41. Tracks crawl; the clock climbs. As it crosses the cue's `at_ts`, the **#1 cue reticle appears** and the cue panel populates. | `No alerts. Just traffic.` → `08:41 — a cue fires.` | The reveal must feel *earned*. If play is too slow, nudge `Shift+→`. Pause the instant the reticle appears. |
| 3 | 14–22 | **Pause.** The right rail now shows **PRIMARY CUE · Yi Peng 3 · 0.83** (alert feed) and **TASK-NEXT QUEUE #1 · SAR · 0.88**. Slowly mouse to the **#1 cue card** (do *not* dwell on the raw alert-feed numbers — see gotcha). | `Task-next queue · #1` | **CAP 13a** (rail close-up). |
| 4 | 22–32 | Click **TASK SAR** on #1. Map eases to the cue box near Bornholm: the **#1 · SAR · 0.88** reticle + **Yi Peng 3 0.83** sitting on the **cable crossing** (orange cables). | `Dark approach · over a live cable` | The money frame. **CAP 12 / 13** (full screen). Hold 2s after the ease settles. |
| 5 | 32–42 | Mouse over the **#1 cue "why"** so it's legible, then the **term bars**: INFRA, RISK, **LIVE (full)**, **SAR (full)**, DARK. | `Why: SAR-confirmed · loitering · bad record` | Reinforces interpretability. Zoom the recording / use a subtle highlight on the why-text in edit. |
| 6 | 42–50 | Click the **Yi Peng 3** marker (or its alert-feed card) → map flies to it; the PRIMARY CUE pin + breakdown (`SAR +0.50  behaviour +0.33`) are visible. | `Suspect: Yi Peng 3 · MMSI 414270000` | **CAP 13b**. This is the "named, blind" payoff. |
| 7 | 50–52 | Quick **freeze** on the suspect + #1 cue together. | `Scored point-in-time · no look-ahead` | The honesty beat, on screen. |
| 8 | 52–66 | **Nord Stream tag (optional in 75s, drop for 45s).** Drag the scrubber to the **NORD STREAM tick** (far left); fine-tune with `Shift+→`/`→` until the cue header reads `Nord Stream · cued as-of 2022-09-26 06:00Z`. Click **TASK SAR #1**. Map fills with the **red dark-contact field**. | `Nord Stream · no AIS suspect` → `153 radar contacts · 0 broadcasting` | **CAP 8** (SAR/dark-density). Point at the **map + cue panel**, *not* the alert feed (it lists rescue/fishing vessels). |
| 9 | 66–75 | Pull back to a clean wide of the dark-contact field with the **#1 · SAR · 1.00** box; slow fade. | `HEIMDALL.ai — the watch for the seabed front` | End card / wordmark over the last frame, or hard cut to the deck's slide 15. |

**Total ≈ 75s.** For the **45s short**: shots 1–6 only, trim each hold by ~1s, end on shot 7.
**15s teaser:** shot 2 reveal (3s) → shot 4 money frame (5s) → shot 6 named suspect (4s) → wordmark (3s).

---

## 3. Screenshots to grab (for the static deck)

Grab these as **full-res PNG** during a paused take (sharper than video frames). Map each to its slide in PITCH.md §6.

| CAP | Slide | Frame | How to get it |
|---|---|---|---|
| **4** | 4 (swarm) | Thousands of vessel tracks, lonely satellite feel | Start state, then **zoom out 1–2 steps** (− button) to show the whole Baltic dense with tracks. Pause. |
| **7** | 7 (scoring) | The alert feed close-up with a scored vessel + breakdown (`SAR +0.50 behaviour +0.33`) | C-Lion1 start; crop the right rail's PRIMARY CUE card. |
| **8** | 8 (SAR) | The **red dark-contact field** (Nord Stream) — our best "radar ground truth" asset | Shot 8 above, full screen. Also export a crop of just the contact cluster. |
| **9** | 9 (geography) | Criticality / cables + infra over the Baltic | Toggle on more infra layers (power cables, naval bases, platforms) and the strategic heatmap; zoom to Baltic. |
| **11** | 11 (the gap — money slide) | Composite: AIS tracks layer **vs** the dark-contact layer, gap in red | Two captures (vessels-only, then dark-contacts-only at the same extent) → composite in design. This is the deck's hero — don't rush it. |
| **13** | 13 (verdict/cockpit) | The #1 cue card + map reticle + named suspect | Shot 4/6 frames. |

---

## 4. Capture gotchas (learned from the real app)

- **Don't sell the raw alert feed.** In C-Lion1 the feed shows *other* vessels at **1.00** above Yi Peng 3's **0.83** (they ran dark but aren't near infra). The *product* is the **TASK-NEXT QUEUE**, where the fused score puts Yi Peng 3 **#1 at 0.88**, and the **PRIMARY CUE** pin marks it. Frame on the queue + pin; let the feed be ambient. In Nord Stream the feed lists *rescue/fishing* vessels — same rule: point at the map's red field and the cue panel.
- **Two reticles look similar.** The **#1 cue box** reticle and a **selected-vessel** reticle are both corner-brackets. After TASK SAR they sit adjacent (box vs. the Yi Peng 3 marker on the cable). Narrate it ("the box we'd task — and the ship driving it") so it doesn't read as a dupe.
- **The cue is gated to `at_ts`.** It will *not* appear before 08:41Z on the incident day — that's the no-look-ahead promise enforced in code (`activeScenario`). Good: it means the "play forward until it fires" reveal is honest, not staged. Don't seek *past* and back across midnight repeatedly — start before, play through once.
- **Label clutter when zoomed out.** At Baltic-wide zoom, vessel labels overlap into a messy block. Either zoom in (cue-box view is clean) or accept it only for the "overwhelmed by traffic" swarm shot (where clutter is *the point*).
- **Basemap tiles stream.** Give the EOX Sentinel-2 basemap a second to sharpen after a big pan before grabbing a still.
- **Speed matters on screen.** Record pans/plays at **600×**; faster speeds make tracks jump. For the reveal, 600× is the sweet spot.

---

## 5. Editing & delivery

- **Captions:** monospaced, lower-third, one line, fade in/out. Numbers only where they land (`0.88`, `MMSI 414270000`, `153 contacts`). Keep them true to §5 of PITCH.md (no "before the cut"; "scored blind, same morning").
- **No music** for the under-speaker cut. For the social/VO cut, low tension bed, ducked.
- **End frame** flows into the deck's slide 15 wordmark — match the black.
- **Redundancy:** export MP4 → (a) embedded in the .pptx, (b) a local file on the presenting laptop, (c) a copy on a phone, (d) an unlisted upload link. The whole point of this asset is to survive failure.
- **Re-shoot trigger:** if `c-lion1.json` / `nord-stream.json` are regenerated (different score or contact count), re-verify the on-screen numbers against PITCH.md §5 and re-cut.

---

## 6. One-paragraph "why this exists"

The hero demo is the pitch. A live demo on venue WiFi, against a map that streams tiles, in front of a jury, on a clock — is a coin flip. This video makes the outcome deterministic: the speaker can run it live *or* play this and narrate over it, and the room can't tell the difference. Record it early in the week, watch it back as a stranger would, and fix anything that needs a sentence of explanation.
