# hackathon-EDTH2026

**Maritime cueing engine for Baltic undersea infrastructure protection.**
Pre-event data preparation for [EDTH 2026 Paris](https://luma.com/edth-2026-paris), June 12–14.

---

## What this project does

**Heimdall** ingests AIS, satellite (SAR) detections, and strategic infrastructure layers — then outputs prioritised ISR tasking recommendations: *"point the next satellite pass at this ~50 km box, here's why."* It runs continuously: a fixed fleet of satellites is re-tasked on a cadence, every vessel is scored point-in-time with **no look-ahead**, and the C-Lion1 / Yi Peng 3 replay shows the engine catching the anchor-drag.

The full project plan lives in [`PLAN.md`](PLAN.md). The threat-model context — Nord Stream, Balticconnector, C-Lion1, Estlink 2 / Eagle S, Latvia–Sweden / Vezhen, Elisa / Fitburg — is described there.

**The app is built.** The React + MapLibre/deck.gl dashboard (`frontend/`) and the Python scoring/cueing engine (`scoring/`) are in this repo — see [Launch Heimdall](#launch-heimdall) to run it. The demo runs with **zero AWS**: the cues, overlays, the hero-incident AIS replay days, and the trained SAR weights all ship in git. What's *not* committed is the rest of the multi-year AIS replay archive and raw imagery (gitignored) — those rebuild from public sources via `scripts/` (see [`DATA_GUIDE.md`](DATA_GUIDE.md)).

---

## Launch Heimdall

The dashboard is a Vite + React + MapLibre/deck.gl app in [`frontend/`](frontend/). The committed data (scoring cues, the satellite-tasking timeline, geo/infrastructure overlays, incidents) ships in git, so the map and cues work out of the box. Prerequisite: **Node 18+**.

```bash
cd frontend
npm install
npm run dev          # → http://localhost:5173
```

It opens on the **C-Lion1 / Yi Peng 3 catch (2024-11-18 09:00Z)** — Yi Peng 3 is satellite #1. Drag the timeline left into 2024-11-17 to watch the engine re-task its 3 satellites every 3 hours through the lead-up; scrub to 2022-09-26 for the Nord Stream dark-density cue. Production-like build: `npm run build && npm run preview` (→ :4173).

### Continuous scoring — run the backend too (optional)

The two incident windows above are **precomputed** and work with no backend. To get **continuous** scoring at *any* instant (scrub anywhere → the engine scores that moment on demand), run the FastAPI backend alongside the frontend:

```bash
source .venv/bin/activate
cd backend && uvicorn app.main:app --port 8077    # the frontend calls :8077 by default
```

The frontend then fetches `/frame?at=<t>` for times outside the precomputed windows (snapped to the 3h cadence + cached, so playback within a window is free; the first request for a new region runs a real ~60-day lookback, a few seconds, shown as "scoring theatre…"). Override the URL with `VITE_BACKEND_URL` if you run it on a different port. Interactive API docs at `http://localhost:8077/docs`.

### The AIS replay tiles

The **hero-incident days are committed**, so a fresh clone already shows a moving fleet on every incident day — no rebuild, no backend. The rest of the multi-year archive is gitignored and rebuilds locally from the public Danish AIS source (no AWS):

| data | path | in git? | how to get it |
|---|---|---|---|
| Scoring cues + satellite timeline | `frontend/public/data/cues/` | ✅ committed | — |
| Geo / infra / incident overlays | `frontend/public/data/*.json` | ✅ committed | — |
| Hero-incident AIS replay days | `frontend/public/data/ais_v2/` | ✅ committed | Nord Stream 2022-09-26, Balticconnector 2023-10-08, C-Lion1/Yi Peng 3 2024-11-17 & 2024-11-18, Estlink2/Eagle S 2024-12-25, LV–SE 2025-01-26 |
| Full AIS replay archive (~3.5 GB, 1601 days) | `frontend/public/data/ais_v2/` | ❌ gitignored | rebuild from public Danish AIS ↓ |
| Trained SAR weights | `scoring/weights/yolov8n_hrsid_best.pt` | ✅ committed | — |

**Rebuild the full archive** — fully local, no AWS. For each day, download the public Danish AIS, build the per-day track tile, then stitch:

```bash
source .venv/bin/activate
python scripts/ingest/danish_ais.py date 2024-11-18   # downloads from Danish Maritime Authority → data/ais/parquet/
python scripts/ingest/build_ais_tracks.py 2024-11-18  # reads local parquet → frontend/public/data/ais/
python scripts/ingest/stitch_tracks.py                # → frontend/public/data/ais_v2/
```

### Regenerate the scoring / cues (optional — they're committed)

```bash
source .venv/bin/activate
python -m scoring.zone_score --emit frontend/public/data/cues   # cues + c-lion1 satellite time-series
python -m unittest discover -s scoring/tests -p 'test_*.py'      # the scoring tests
python -m scoring.validate_fleet --as-of 2024-11-18              # the no-overfit fleet check
```

---

## Data prep (the rest of this repo)

The bulk of this repo is the **data-prep layer** that feeds the engine — AIS, satellite imagery, criticality layers, sanctions, incidents. Setup below.

1. Clone the repo: `git clone https://github.com/alexisrichard/hackathon-EDTH2026.git`
2. Follow [`ONBOARDING.md`](ONBOARDING.md) — cross-platform (Windows winget, macOS Homebrew). ~15 min; no AWS needed.
3. Regenerate any full dataset you need from its public source via `scripts/` — per-source commands in [`DATA_GUIDE.md`](DATA_GUIDE.md). (Only some sources need keys: Copernicus / Kaggle / GFW / Equasis.)
4. Open `data/samples/notebooks/01_baltic_exploration.ipynb` for a quick tour of the data.

### Using AI coding assistants (Claude, Gemini, ChatGPT/Codex…)

The repo's working guide is [`AGENTS.md`](AGENTS.md) — one **tool-neutral** source of truth for humans and any AI assistant. [`CLAUDE.md`](CLAUDE.md) and [`GEMINI.md`](GEMINI.md) are thin pointers that redirect those tools to it (Codex/ChatGPT read `AGENTS.md` natively), so whatever you use auto-loads the same rules — just `cd` into the repo and start. It briefs you on the system design, the data layout and conventions (Baltic bbox, parquet partitioning, public-source rebuilds), the commands, and our way of working (branch isolation — never commit to `main`; plan-first; verify-before-done). It's also a fast read for humans who want the project in one page. Keep it current as the project evolves.

---

## Data inventory (high level)

📖 **For a specialist-readable, source-by-source guide** — what each dataset is, what it provides, coverage / cadence / volume, what it's useful for, and caveats — see **[`DATA_GUIDE.md`](DATA_GUIDE.md)**.

Full provenance + license matrix in [`data/SOURCES.md`](data/SOURCES.md).
The large files are not committed — they regenerate from their original public sources via `scripts/` (per-source commands in [`DATA_GUIDE.md`](DATA_GUIDE.md)). No AWS/S3 is involved.

| Category | What we have | Source |
|---|---|---|
| AIS — bulk historical | **1,601 days** Baltic-filtered Parquet, 2022-01-01 → 2026-05-20 (~330 GB); full 2022→present backfill runs via `scripts\overnight.ps1` | Danish Maritime Authority |
| AIS — live | WebSocket consumer for the Sunday demo | AISStream.io |
| Satellite imagery | 441 Sentinel-1/-2 scenes catalogued; 9 incident-AOI crops downloaded | Copernicus Data Space + Element84 STAC |
| Criticality / infrastructure | 36 GeoJSON layers — cables, pipelines, ports, naval bases, wind farms, refineries, TSS, lighthouses, anchorages, wrecks, fairways, shipping accidents, oil spills, EEZ, bathymetry, chokepoints | OSM, EMODnet, HELCOM, Natural Earth, Marine Regions, GMRT |
| Sanctions | 1,773 maritime entries (OFAC SDN, UK OFSI, EU FSF) | Treasury OFAC, gov.uk, OpenSanctions |
| Shadow fleet | KSE quarterly tracker PDF parsed (managers + buyers); vessel-level dataset awaiting reply from KSE Institute | Kyiv School of Economics |
| Vessel registry | On-demand per-IMO lookup (name, ownership, manager, ISM, classification, port history) | Equasis |
| GFW events | Per-vessel port visits, loitering, encounters, AIS gaps, fishing | Global Fishing Watch v3 API |
| Marine weather | 9 incident windows × hourly waves + wind + temp + pressure | Open-Meteo + ERA5 |
| Incidents | 9 well-sourced Baltic events Sep 2022 → Jan 2026 with attribution taxonomy | Hand-curated |
| Kaggle | **10 datasets (~24 GB, 63k files), rebuildable from Kaggle:** SeaDronesSee drone video, HRSID + LS-SSDD + SARScope (SAR), ships-in-satellite (optical), AFO (aerial), Kattegat AIS, daily port activity, world ports, Ukraine-war events | Kaggle |

---

## Repo layout

> **Working in a team? Read [`REPO_STRUCTURE.md`](REPO_STRUCTURE.md)** — directory ownership lanes, the branch-per-person model, and a "where do I put X" guide.

```
.
├── AGENTS.md                       project guide for humans + AI assistants (source of truth)
├── CLAUDE.md, GEMINI.md            thin pointers → AGENTS.md (per-tool auto-load)
├── REPO_STRUCTURE.md               repo map: ownership lanes + where things go
├── PLAN.md                         project plan (what we're building during the hackathon)
├── ONBOARDING.md                   team setup, cross-platform
├── README.md                       this file
│
├── data/
│   ├── SOURCES.md                  data provenance + license matrix
│   ├── geo/                        criticality layers (small, in git)
│   ├── reference/                  incidents, sanctions, KSE, marine weather (small, in git)
│   ├── ais/                        local AIS parquet (gitignored — rebuild via scripts/ingest/danish_ais.py)
│   ├── optical/                    Sentinel-2 crops (gitignored — rebuild from Copernicus)
│   ├── sar/                        Sentinel-1 crops (gitignored — rebuild from Copernicus)
│   └── samples/notebooks/          starter notebook
│
├── scripts/
│   ├── common/                     helpers (DuckDB connection, bbox constants; sync_from_s3.py is a retired no-op)
│   ├── geo/                        criticality-layer fetchers (OSM, EMODnet, HELCOM, ...)
│   ├── ingest/                     bulk + streaming + satellite + Kaggle fetchers
│   ├── reference/                  sanctions, KSE PDF parser, Equasis lookup
│   ├── ingest/stitch_tracks.py     build the stitched AIS replay tiles (ais_v2)
│   └── overnight.ps1               one-shot launcher for the heavy bulk downloads
│
├── frontend/                       Heimdall dashboard — Vite + React + MapLibre/deck.gl
│   └── public/data/                committed cues + overlays (ais_v2 replay tiles gitignored)
│
├── scoring/                        point-in-time ship-trust + zone (cueing) engine + tests
│
├── outreach/                       drafted emails, signup guides, team recaps (HTML + text)
│
└── requirements.txt                Python deps (geopandas, duckdb, boto3, pyais, ...)
```

---

## Where the credentials live

The demo needs **no credentials at all** — it runs entirely from data committed in git. Keys are only for OPTIONAL full-dataset rebuilds. All gated sources read from `.env.local` at the repo root (gitignored). The keys we use:

- `COPERNICUS_CLIENT_ID` + `COPERNICUS_CLIENT_SECRET` — Sentinel imagery (rebuild only)
- `GFW_API_TOKEN` — Global Fishing Watch v3 API (rebuild only)
- `EQUASIS_USERNAME` + `EQUASIS_PASSWORD` — vessel registry lookup (rebuild only)
- `AISSTREAM_API_KEY` — live AIS WebSocket (optional live mode)
- Kaggle: `~/.kaggle/kaggle.json` — the 10 Kaggle ML datasets (rebuild only)

**AWS/S3 is no longer used.** The project bucket has been retired and deleted; nothing reads from it, and no `aws configure` is needed. The Danish AIS rebuild downloads from the public source with no credentials.

**The remaining keys above should be rotated after the hackathon** (they live in AI-assistant chat history where they were originally pasted in). The AWS keys are moot now that the bucket is gone.

---

## Overnight bulk download

Most bulk downloading is deliberately deferred to overnight so it doesn't compete with active work:

```powershell
powershell -File scripts\overnight.ps1
```

Launches three detached background processes:
- Danish AIS full backfill 2022→present (~70 h, skip-if-exists idempotent)
- 10 Kaggle datasets (drone video, SAR, optical, AIS samples)
- GFW per-vessel events for the named incident suspects

Logs land at `data/cache/overnight_*.log`. Safe to interrupt and restart.

---

## Honest gaps

- **KSE vessel-level shadow-fleet list** — the public quarterly tracker is aggregate stats only. Emailed KSE Institute requesting the per-vessel dataset; awaiting reply.
- **Finnish bulk historical AIS** — Digitraffic API works per-MMSI but historical depth is shallow. Mitigated by Danish AIS partially covering the Gulf of Finland.
- **Orange Marine cable routes** — potential authoritative-source data if Alexis's CEO contact comes through.

---

## License + attribution

Mixed-license project. See [`data/SOURCES.md`](data/SOURCES.md) for the full matrix.

For any public demo or pitch deck, include the attribution string from `SOURCES.md` (it covers OSM ODbL, Copernicus, EMODnet, Marine Regions, HELCOM, AIS providers, sanctions sources).

Two **non-commercial** datasets are included for hackathon use that would need to be replaced/licensed for a commercial product: OpenSanctions (EU FSF feed) and Capella Open Data SAR samples. Flagged in `SOURCES.md` § "Commercial-use guardrails."

---

## Team

EDTH 2026 Paris hackathon team of three:
- Engineer / entrepreneur (telecom, cyber, submarine cables) — [Alexis Richard](https://www.linkedin.com/in/alexis-richard-77053857/)
- Engineer
- Cyber + defense

Repository owner: [@alexisrichard](https://github.com/alexisrichard).
