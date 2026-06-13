# backend/ — API service

**Lane:** Data & Backend · **Owner:** _Alexis / TBD_

The typed data layer the dashboard hangs off. Serves vessel tracks, interpretable
suspicion scores, ranked ISR "task-next" cues, the criticality grid, and the
incident/scenario catalogue. **Mock-first:** it runs with zero AWS/network setup
so the frontend can build against realistic typed JSON immediately; the real
DuckDB-over-S3 path swaps in behind the same interface.

**Stack:** FastAPI + uvicorn, pydantic v2 models (the single source of truth),
DuckDB (`httpfs` over S3) for the real data path.

## How data flows

```
                 mock (default)                         duckdb (DATA_SOURCE=duckdb)
                 ──────────────                         ───────────────────────────
S3 AIS parquet ─┐                              S3 AIS parquet ──► DuckDB httpfs ──┐
data/geo/*      ├─ (not touched in mock)       data/geo/*       ──► criticality   ├─► DataSource
                │                              scoring.score    ──► suspicion     │
   scripted ────┘                                                                 │
   Eagle S scenario ──────────────► DataSource ◄───────────────────────────────────┘
                                        │
                          pydantic models (app/models)  ──►  FastAPI routers (app/routers)
                                        │                            │
                          display hints (app/core/display.py,        ▼
                          from shared/encoding/display_encoding.json)   JSON  ──►  frontend
```

- **`DataSource`** (`app/data/base.py`) is the seam. Two implementations:
  - **`MockDataSource`** — the default. A scripted, realistic recreation of the
    **Eagle S / Estlink 2** incident (25 Dec 2024, Gulf of Finland): the tanker
    *EAGLE S* slows over the real Estlink 2 cable route and its collection
    priority climbs over time, while a RoPax ferry, a container ship, a fishing vessel, and an
    anchored bulker stay calm. Includes a criticality grid with a hotspot over the
    cable and a top-K SAR cue pointing at it. Everything is a pure function of the
    requested instant `t`, so `/scores` and `/cues` re-rank live as the clock scrubs.
  - **`DuckDBDataSource`** — reads AIS parquet from S3 via DuckDB `httpfs`
    (reusing `scripts/common/duck.py`). `/vessels` is a real query; the
    scoring-dependent endpoints (`/scores`, `/cues`, `/geo`) delegate to the
    mock integration until real feature extraction and the criticality grid
    land. The mock integration already calls `scoring.score_observation` and
    `scoring.rank_tasking`.
- Models live in `app/models/` and are the source of truth. The frontend mirrors
  them 1:1 in `frontend/src/types/`.
- Shape/color **display encoding** is shared with the frontend via
  `shared/encoding/display_encoding.json` (served at `GET /encoding`), so backend
  hints and frontend rendering never drift.

## Run (mock mode — the default)

From this `backend/` directory, with the **root** `.venv` active:

```bash
# one-time: install backend deps into the root venv (from repo root)
#   pip install -r requirements.txt        # or just the API deps:
#   pip install "fastapi>=0.110" "uvicorn[standard]>=0.27" "pydantic>=2.5"

source ../.venv/bin/activate
uvicorn app.main:app --reload            # DATA_SOURCE defaults to mock
```

Then:

```bash
curl localhost:8000/health
curl "localhost:8000/scores?t=2024-12-25T13:50:00Z" | python -m json.tool | head
curl "localhost:8000/cues?t=2024-12-25T13:50:00Z&top=3"
open http://localhost:8000/docs          # interactive Swagger UI
```

The demo instant `2024-12-25T13:50:00Z` shows EAGLE S already hot (SAR cue firing)
*before* the 14:00 cable cut — the hero narrative.

## Run against real S3 data (duckdb mode)

Requires AWS creds (`aws configure`, region `eu-west-3`) and reachable S3.

```bash
DATA_SOURCE=duckdb uvicorn app.main:app --reload
# example working query proving the httpfs/S3 path:
#   from app.data.duckdb_source import DuckDBDataSource
#   DuckDBDataSource().count_positions(2024, 12, 25)
```

## Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | liveness + active data source |
| `GET /encoding` | shared shape/color display encoding |
| `GET /vessels?bbox=&start=&end=&limit=` | vessel tracks (bbox + window) |
| `GET /scores?bbox=&t=` | per-vessel suspicion + breakdown + display hints at `t` |
| `GET /cues?bbox=&t=&top=` | top-N task-next recommendations at `t` |
| `GET /geo/criticality?bbox=&t=` | criticality + cueing grid at `t` |
| `GET /scenarios` · `GET /scenarios/{id}` | named demo replays |
| `GET /incidents` | ground-truth incident catalogue |

Conventions: coords `[lon, lat]` EPSG:4326, times ISO-8601 UTC, region `eu-west-3`.
Full shapes in [`../shared/api_contract.md`](../shared/api_contract.md); the
always-current spec is `/openapi.json`.

## Layout

```
app/
├── main.py            # FastAPI app: routers, CORS, /health, /encoding
├── core/
│   ├── paths.py       # puts repo root on sys.path (so `scripts.*` imports work)
│   ├── config.py      # env-driven settings (DATA_SOURCE), S3 layout
│   └── display.py     # shape/color from shared/encoding/display_encoding.json
├── models/            # pydantic v2 domain models — the single source of truth
├── data/
│   ├── base.py        # DataSource ABC (the seam)
│   ├── mock.py        # MockDataSource (default) + incidents.csv loader
│   ├── mock_scenario.py # scripted Eagle S / Estlink 2 fleet + score arcs
│   └── duckdb_source.py # DuckDB-over-S3 (real /vessels; scoring stubs delegate)
└── routers/           # /vessels /scores /cues /geo /scenarios /incidents
```

See [`../REPO_STRUCTURE.md`](../REPO_STRUCTURE.md) and [`../PLAN.md`](../PLAN.md) §5–6.
