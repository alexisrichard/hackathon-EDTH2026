# REPO_STRUCTURE.md — the map

How this repo is organized, **who owns what**, and **where to put a new thing**. Read this before you start writing code. It exists so three people can work in parallel without clobbering each other.

> **The one rule that prevents merge hell:** *own your directory.* Each person works inside their lane. Touching another lane's directory means a PR + a heads-up to its owner. Combined with one-branch-per-person (see [`AGENTS.md`](AGENTS.md) → Collaboration), this keeps conflicts near zero.

The app stack below (FastAPI, React + MapLibre/deck.gl, scikit-learn/lightgbm) is [`PLAN.md`](PLAN.md)'s suggested default — **confirm or change it together Friday**, then update this file. The *directory layout* and *ownership model* hold regardless of stack.

---

## 1. Top-level layout

```
hackathon-EDTH2026/
│
├── AGENTS.md            # project guide for humans + AI assistants — the source of truth
├── CLAUDE.md, GEMINI.md # thin pointers → AGENTS.md (so each tool auto-loads it)
├── REPO_STRUCTURE.md    # THIS FILE — what goes where, who owns what
├── PLAN.md              # full system design, scope tiers, demo flow, threat model
├── ONBOARDING.md        # machine setup (venv, AWS, smoke tests)
├── README.md            # project overview + data inventory
├── requirements.txt     # ALL Python deps (data-prep + backend + scoring) — one root .venv
│
├── data/                # ░ DATA lane ░ datasets
│   ├── geo/             #   criticality layers — small, COMMITTED (.geojson)
│   ├── reference/       #   sanctions, incidents, KSE, weather — small, COMMITTED
│   ├── ais|sar|optical/ #   big regenerable data — GITIGNORED (rebuild via scripts from public sources)
│   └── samples/notebooks/   starter notebook
│
├── scripts/             # ░ DATA lane ░ data-prep pipelines (mostly complete — stable)
│   ├── common/          #   shared helpers: bbox, DuckDB conn (local parquet); sync_from_s3 retired  ← import these everywhere
│   ├── ingest/          #   AIS / satellite / Kaggle fetchers
│   ├── geo/             #   criticality-layer fetchers (OSM, EMODnet, HELCOM, …)
│   └── reference/       #   sanctions, KSE PDF parser, Equasis lookup
│
├── backend/             # ░ BACKEND lane ░ FastAPI service — the API the frontend calls
│   ├── app/
│   │   ├── main.py      #   app entrypoint
│   │   ├── routers/     #   /vessels  /scores  /cues  /incidents  /scenarios
│   │   └── data/        #   DuckDB query layer (reads LOCAL ais/ parquet, geo layers)
│   └── README.md
│
├── scoring/             # ░ ML lane ░ the suspicion engine (importable Python package)
│   ├── coherence/       #   per-class behavioral models (fishing, tanker, container, …)
│   ├── kinematic/       #   kinematic-anomaly features (speed, course-change, stops)
│   ├── criticality/     #   criticality-surface lookup (reads data/geo)
│   ├── score.py         #   combines the terms → suspicion(vessel, t)   [PLAN.md §5.4]
│   ├── train/           #   training scripts + experiment notebooks
│   └── README.md
│
├── frontend/            # ░ FRONTEND lane ░ React + MapLibre/deck.gl dashboard
│   ├── src/
│   │   ├── components/  #   Map, AlertFeed, CueingPanel, TimeScrubber
│   │   └── api/         #   typed client → backend
│   ├── package.json
│   └── README.md
│
├── shared/              # ░ CONTRACTS ░ the interfaces between lanes — change via PR + ping
│   ├── api_contract.md  #   backend ↔ frontend API shape (source of truth)
│   ├── scenarios.json   #   named incident scenarios for replay (date, AOI, narrative)
│   └── README.md
│
└── outreach/            # ░ LEAD ░ pitch deck, demo script, team comms, recaps
```

---

## 2. Ownership lanes

Assign one person per lane **Friday morning**, then write the names in. Whoever owns a lane owns its directory and its branch namespace.

| Lane | Owner | Directories | Builds | Depends on |
|---|---|---|---|---|
| **Data & Backend** | _Alexis / TBD_ | `backend/`, `scripts/`, `data/` | local-parquet/DuckDB access, FastAPI serving tracks + scores + cues, scenario replay endpoints | `scoring.score`, `shared/api_contract.md` |
| **ML & Scoring** | _TBD_ | `scoring/` | behavioral coherence + kinematic anomaly + criticality → one suspicion score | `data/`, `scripts/common` |
| **Frontend & Demo** | _TBD_ | `frontend/`, demo script + backup video | the dashboard (map, alert feed, cueing panel, scrubber), the live demo | `backend` API, `shared/api_contract.md` |
| **Shared / Lead** | _Alexis_ | `shared/`, `outreach/`, `PLAN.md`, `README.md` | API contract, demo scenarios, pitch, keeping the team unblocked | everyone |

The data-prep work (`scripts/`) is largely done — that lane's real day-of job is the **backend**. ML and Frontend are net-new.

---

## 3. "Where do I put X?"

| I'm adding… | It goes in… |
|---|---|
| A new data/AIS/satellite fetcher | `scripts/ingest/` |
| A query that reads AIS parquet (local `data/ais/parquet/`) | `backend/app/data/` (or `scripts/common/` if broadly reusable) |
| A new vessel-class behavior model | `scoring/coherence/` |
| The formula combining the score terms | `scoring/score.py` |
| A new map layer or UI panel | `frontend/src/components/` |
| A new API endpoint | `backend/app/routers/` **and** update `shared/api_contract.md` |
| A criticality GeoJSON layer (small) | `data/geo/` — commit it |
| A big derived file (parquet, GeoTIFF, >10 MB) | local `data/ais\|sar\|optical/` (gitignored, regenerable via scripts), **not** git — see `.gitignore` |
| A new incident scenario for the demo | `shared/scenarios.json` (curate from `data/reference/incidents.csv`) |
| Pitch deck / demo video / outreach | `outreach/` |
| A throwaway exploration notebook | your lane's dir, or `data/samples/notebooks/` |
| A shared constant (bbox, CRS) | already in `scripts/common/bbox.py` — import, don't redefine |

---

## 4. The contracts (where lanes meet)

Agree on these **early Friday**, then mock each side so nobody is ever blocked (mock-first philosophy, [`PLAN.md`](PLAN.md) §10.3):

- **Backend ↔ Frontend** → `shared/api_contract.md`. The JSON shapes for `/vessels`, `/scores`, `/cues`, `/scenarios`. Frontend codes against the documented shape with a mock fixture until the live endpoint exists.
- **Backend ↔ Scoring** → the `scoring.score.suspicion(...)` signature. Backend calls a stub returning random scores until the real engine lands, then swaps it in. The interface is the handshake — agree on inputs (a vessel track + time) and output (a 0–1 score + per-term breakdown) first.
- **Everyone ↔ Data** → `scripts/common/bbox.py` (`BALTIC_BBOX`), the local `data/` layout (`AGENTS.md` §2), and `shared/scenarios.json` for demo dates/AOIs.

---

## 5. Conventions (recap — full list in AGENTS.md §2)

- **Region** `eu-west-3`. **CRS** EPSG:4326. **Baltic bbox** 52–66°N / 9–30°E (`scripts.common.bbox`).
- **Parquet partitioning** `year=YYYY/month=MM/day=DD/`.
- **One root `.venv`** for all Python (data-prep + backend + scoring); frontend has its own `frontend/package.json`. Add new Python deps to the root `requirements.txt`.
- **Never commit** `.env*`, secrets, raw AIS, anything under `data/ais|sar|optical/`, the venv. **Always commit** code you wrote, small GeoJSON under `data/geo/`, CSVs under `data/reference/`.
- **`main` stays demoable** at all times — it's the live demo. Merge small, merge often.
