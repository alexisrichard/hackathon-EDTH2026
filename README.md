# hackathon-EDTH2026

**Maritime cueing engine for Baltic undersea infrastructure protection.**
Pre-event data preparation for [EDTH 2026 Paris](https://luma.com/edth-2026-paris), June 12–14.

---

## What this project does (and what's in this repo *right now*)

The hackathon target is a system that ingests AIS, satellite imagery, and strategic infrastructure layers — then outputs prioritised ISR tasking recommendations: *"point the next satellite pass at this 50 km box at 14:00, here's why."*

The full project plan lives in [`PLAN.md`](PLAN.md). The threat-model context — Nord Stream, Balticconnector, C-Lion1, Estlink 2 / Eagle S, Latvia–Sweden / Vezhen, Elisa / Fitburg — is described there.

**This repository, in its current state, is *only* the data-prep layer.** Every dataset we identified is either downloaded, scripted, or honestly documented as a gap. The model, the scoring engine, the dashboard, the demo — all of that is hackathon-weekend work and is deliberately not pre-built here.

---

## Quick start

1. Clone the repo: `git clone https://github.com/alexisrichard/hackathon-EDTH2026.git`
2. Follow [`ONBOARDING.md`](ONBOARDING.md) — cross-platform (Windows winget, macOS Homebrew). ~30 min including AWS configuration.
3. Get the bucket access key from Alexis (private channel — not in the repo).
4. Open `data/samples/notebooks/01_baltic_exploration.ipynb` for a quick tour of the data.

---

## Data inventory (high level)

📖 **For a specialist-readable, source-by-source guide** — what each dataset is, what it provides, coverage / cadence / volume, what it's useful for, and caveats — see **[`DATA_GUIDE.md`](DATA_GUIDE.md)**.

Full provenance + license matrix in [`data/SOURCES.md`](data/SOURCES.md).
Source of truth for the large files: `s3://edth2026-baltic/` (eu-west-3).

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
| Kaggle | 10 datasets queued for download (drone-video SDS, HRSID, LS-SSDD, MASATI, AFO, ports, Kattegat AIS, etc.) | Kaggle |

---

## Repo layout

```
.
├── PLAN.md                         project plan (what we're building during the hackathon)
├── ONBOARDING.md                   team setup, cross-platform
├── README.md                       this file
│
├── data/
│   ├── SOURCES.md                  data provenance + license matrix
│   ├── geo/                        criticality layers (small, in git)
│   ├── reference/                  incidents, sanctions, KSE, marine weather (small, in git)
│   ├── ais/                        local AIS mirror (gitignored — see S3)
│   ├── optical/                    Sentinel-2 crops (gitignored — see S3)
│   ├── sar/                        Sentinel-1 crops (gitignored — see S3)
│   └── samples/notebooks/          starter notebook
│
├── scripts/
│   ├── common/                     helpers (DuckDB connection, S3 sync, bbox constants)
│   ├── geo/                        criticality-layer fetchers (OSM, EMODnet, HELCOM, ...)
│   ├── ingest/                     bulk + streaming + satellite + Kaggle fetchers
│   ├── reference/                  sanctions, KSE PDF parser, Equasis lookup
│   └── overnight.ps1               one-shot launcher for the heavy bulk downloads
│
├── outreach/                       drafted emails, signup guides, team recaps (HTML + text)
│
└── requirements.txt                Python deps (geopandas, duckdb, boto3, pyais, ...)
```

---

## Where the credentials live

All gated sources read from `.env.local` at the repo root (gitignored). The current keys we use:

- `AISSTREAM_API_KEY` — live AIS WebSocket
- `EQUASIS_USERNAME` + `EQUASIS_PASSWORD` — vessel registry lookup
- `COPERNICUS_CLIENT_ID` + `COPERNICUS_CLIENT_SECRET` — Sentinel imagery
- `GFW_API_TOKEN` — Global Fishing Watch v3 API

AWS access (S3) is configured via `aws configure` and lives in `~/.aws/credentials`. The `edth2026-data` IAM user has S3 access to the project bucket.

**All of the above should be rotated after the hackathon.** They live in chat history with Claude where they were originally pasted in.

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
