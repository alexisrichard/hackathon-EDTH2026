# frontend-plan.md — the cockpit + the demo

**Lane:** Frontend & Demo (Alexis). This is the endgame the rest of the project builds toward. Living doc — edit freely.

---

## 1. North star (what the jury sees)

A **Palantir-style operations map** of the **Baltic + North Sea** that **replays the war-era incident timeline**. As time runs, our cueing engine colors the vessels and lights up the zones it thinks are worth a satellite pass. The payoff: the ships and areas where the **real incidents** happened light up — *including incidents the model was never trained on.*

> "It's Dec 24, 2024. Watch Eagle S slow over Estlink 2, watch its color go hot, watch the engine recommend tasking this 30 km box — and the cable goes down 14 minutes later. We never showed the model this incident."

---

## 2. The interface

A full-screen, pannable / zoomable map — dark "ops" aesthetic. Baltic + North Sea in view, free movement around the theatre.

**Candidate stack:** MapLibre GL (base map + interaction) with deck.gl for the heavy data layers (thousands of vessels, GPU-rendered). Confirm day-of.

---

## 3. Overlays (toggle on/off, stack on top of the base map)

1. **Geo — strategic criticality heatmap.** Everything of interest (cables, pipelines, naval bases, ports, wind farms, chokepoints…) compiled into a **fine heatmap of how "strategic" each zone is.** This is the spatial weight the scoring multiplies by. *(Fed by Gabriel's North Sea + Baltic grid + the `data/geo/` layers.)*
2. **AIS — live vessels.** Every ship moving on the map. Rendering is **programmatically controlled**:
   - **shape → ship type** (tanker, cargo, fishing, RoPax, military aux, …)
   - **color → suspicion score** (straight from the scoring engine — hot = flagged)
3. **Satellite recommendations — the core of the product.** An overlay of the **top-K zones we recommend checking** with a satellite pass right now (the cueing output). This is what makes us a *cueing engine*, not just an anomaly map. *(Fed by Gabriel's grid + the per-area score.)*
4. **Other — TBD.** Candidates: cable/infra status (flips red on a cut), dark-vessel candidates (radar-vs-AIS), incident markers, EEZ boundaries.

---

## 4. Time control (the replay)

A **time-control panel** drives the whole scene:
- **scrub** to any moment, **play / pause**, **adjust speed**.
- On play, *everything* animates against the clock: vessels move, colors update as scores change, the criticality heatmap stays (mostly static) while the **recommendation overlay re-ranks** live.
- Demo window: the war-era Baltic timeline (Nord Stream Sep 2022 → Latvia–Sweden Jan 2025, and onward).

---

## 5. The "aha" — train/test on real incidents

The thing that makes this land with a defense jury:
- **Train** the scoring system on **60–80%** of the incidents we've catalogued.
- **Hold out** the rest.
- During the replay, the held-out incidents should still **light up correctly** — the right vessel flagged, the right zone recommended — *before* the cable goes down.
- That demonstrates the model **generalizes** (detects the pattern) rather than **memorizes** (replays a script). It's the difference between a demo and a product.

Known incidents to draw from (`data/reference/incidents.csv`, 9 events; 5 with coords in `scripts/common/bbox.py`): Nord Stream, Balticconnector/Newnew Polar Bear, C-Lion1/Yi Peng 3, Estlink 2/Eagle S, Latvia–Sweden.

---

## 6. How the lanes feed this screen

| Overlay / piece | Needs | Owner |
|---|---|---|
| Base map + pan/zoom + time control | the app shell | **Alexis** (frontend) |
| Criticality heatmap | the grid + per-cell strategic score | **Gabriel** (grid) + geo layers |
| Satellite-reco overlay (top-K zones) | per-cell cueing score over the grid | **Gabriel** (grid) + scoring |
| Vessel color (suspicion) | per-vessel score over time | **Côme** (scoring, calibrated on incidents) |
| Vessel shape (type) | AIS `ship_type` field | AIS data (already in S3) |
| Time-sliced vessels + scores + reco | an **API / data layer** serving the frontend per timestep | **unowned — see §7** |

---

## 7. Implementation notes & open questions (Alexis + Claude — not yet decided)

- **Who serves the data?** The frontend needs time-sliced AIS + scores + recommendations per frame. Nobody's explicitly on the backend/API lane yet. Likely a thin FastAPI (or even precomputed static JSON/Parquet tiles) — decide early so the contract (`shared/api_contract.md`) is real.
- **Precompute for demo reliability.** Don't compute scores live during the pitch. Precompute per-timestep vessel scores + per-cell reco for the demo window and serve them as fixtures/tiles. Mock-first (PLAN §10.3) — the demo must not depend on venue WiFi or a live model.
- **Rendering scale.** Baltic AIS is millions of positions/day. Render every ship only via GPU (deck.gl) + server-side spatial/time filtering + sensible downsampling, or the map will crawl. Pick a demo time window and resolution that's smooth.
- **North Sea data gap.** Our prepped data is clipped to `BALTIC_BBOX` (lon 9–30°E); the North Sea is mostly west of 9°E. If the demo map shows the North Sea, we need data there or we show an empty sea. Decide scope with Gabriel.
- **Grid resolution / scheme.** Hex (H3) vs degree/UTM grid — affects both the heatmap and the reco overlay. Align with Gabriel.
- **Overlay #4** — pick what actually sells the story; cable-status-flips-red is the most dramatic.

---

*Next: brand — name, identity, visual language (will inform the map's look & feel).*
