# API contract — backend ↔ frontend

**Source of truth for the JSON shapes the dashboard consumes.** This now matches
the implemented FastAPI backend (`backend/app/`). Change only via PR + a heads-up
(the frontend mocks against this; a silent change breaks it). The interactive,
always-current spec is at **`/docs`** (Swagger) and **`/openapi.json`** when the
server is running.

- **Base URL:** `http://localhost:8000` (dev). Override the frontend client with
  `VITE_API_BASE_URL`.
- **Times:** ISO-8601 UTC strings (e.g. `2024-12-25T13:50:00Z`).
- **Coords:** `[lon, lat]`, EPSG:4326.
- **BBox:** `[min_lon, min_lat, max_lon, max_lat]`. As a *query param* it is the
  comma-separated string `min_lon,min_lat,max_lon,max_lat`.
- **Data source:** `mock` (default) or `duckdb`, via the `DATA_SOURCE` env var.
  Mock serves the realistic Eagle S / Estlink 2 scenario so the frontend works
  with zero backend setup. Default demo instant: `2024-12-25T13:50:00Z`.
- TypeScript types mirror these shapes 1:1 in `frontend/src/types/models.ts`;
  the typed client is `frontend/src/api/client.ts`.

---

### `GET /health`
Liveness + which data source is active.
```jsonc
{ "status": "ok", "data_source": "mock", "version": "0.1.0" }
```

### `GET /encoding`
The shared shape/color display encoding (verbatim
`shared/encoding/display_encoding.json`). Lets a client verify it matches the TS
mirror or recompute display hints itself.

### `GET /vessels?bbox=&start=&end=&limit=`
Vessel tracks in a bbox + time window (replayed from AIS). All params optional;
`limit` defaults to 500.
```jsonc
{ "vessels": [
  { "vessel": {
      "mmsi": 372985000, "name": "EAGLE S", "imo": 9329760, "callsign": "5BWC3",
      "ship_type": "tanker", "cargo_type": null, "length": 228.0, "width": 32.0,
      "draught": 8.4, "flag": "Cook Islands", "destination": "PORT SAID" },
    "track": [
      { "t": "2024-12-25T12:00:00Z", "lon": 26.95, "lat": 59.98,
        "sog": 10.5, "cog": 248, "heading": 248, "nav_status": "under_way_using_engine" }
    ] }
] }
```
> Note: `vessel` is a nested object (richer than the draft's flat shape), and the
> position carries `heading` + `nav_status`.

### `GET /scores?bbox=&t=`
Per-vessel defensive collection priority at instant `t` (defaults to the demo
instant), sorted highest-first, with the five-factor weighted breakdown from
PLAN §5.4. `breakdown.suspicion` remains a compatibility alias for
`breakdown.score`.
```jsonc
{ "t": "2024-12-25T13:50:00Z",
  "scores": [
    { "vessel": { "mmsi": 372985000, "name": "EAGLE S", "ship_type": "tanker", "...": "..." },
      "t": "2024-12-25T13:50:00Z",
      "position": { "t": "2024-12-25T13:50:00Z", "lon": 26.39, "lat": 59.90,
        "sog": 1.6, "cog": 250, "heading": 250, "nav_status": "under_way_using_engine" },
      "breakdown": {
        "infrastructure_proximity": 0.95, "unusual_movement": 0.99,
        "ais_recency": 0.78, "infrastructure_importance": 0.95,
        "satellite_availability": 0.95,
        "contributions": {"infrastructure_proximity": 0.285, "unusual_movement": 0.2475},
        "why": "High observation priority because the vessel is close to protected infrastructure...",
        "disclaimer": "Defensive collection cue only; this score does not assess hostile intent.",
        "score": 0.85, "suspicion": 0.85 },
      "display": { "shape": "triangle", "color": [233, 86, 65], "color_hex": "#e95641", "band": "elevated" } }
] }
```

### `GET /cues?bbox=&t=&top=5`
Top-N areas to task next — the product (PLAN §5.5). Ranked by `score`.
```jsonc
{ "t": "2024-12-25T13:50:00Z",
  "cues": [
    { "rank": 1, "cell_id": "r2c5", "bbox": [26.25, 59.8167, 26.42, 59.975],
      "t": "2024-12-25T14:10:00Z", "sensor": "SAR", "score": 0.88,
      "driver_mmsis": [372985000],
      "why": "Synthetic observations near the Estlink 2 protection corridor; SAR collection is available." }
] }
```
`sensor` ∈ `SAR | optical | AIS | DAS`.

### `GET /geo/criticality?bbox=&t=`
The criticality + cueing grid at instant `t`: per-cell static `criticality` (the
heatmap overlay) and dynamic `cue_score` (drives the satellite-recommendation
overlay).
```jsonc
{ "grid": {
    "t": "2024-12-25T13:50:00Z",
    "bbox": [25.4, 59.5, 27.1, 60.45],
    "cells": [
      { "cell_id": "r2c5", "bbox": [26.25, 59.8167, 26.42, 59.975], "h3": null,
        "criticality": 0.88, "cue_score": 1.0, "driver_mmsis": [372985000] }
    ] } }
```

### `GET /scenarios`  ·  `GET /scenarios/{id}`
Named incident replays (mirrors `shared/scenarios.json`). `/scenarios/{id}`
returns one or 404. `held_out` flags incidents excluded from training
(frontend-plan §5 generalization story).
```jsonc
{ "scenarios": [
  { "id": "eagle-s-2024-12-25", "name": "Eagle S / Estlink 2",
    "start": "2024-12-25T12:00:00Z", "end": "2024-12-25T16:00:00Z",
    "bbox": [25.4, 59.5, 27.1, 60.45], "suspect_mmsi": 372985000,
    "incident_id": "INC-2024-12-25", "narrative": "…", "held_out": true } ] }
```

### `GET /incidents`
The catalogued ground-truth timeline (read from `data/reference/incidents.csv`).
```jsonc
{ "incidents": [
  { "incident_id": "INC-2024-12-25", "name": "Estlink 2 + 4 telecom cables cut (Eagle S)",
    "date_utc": "2024-12-25", "time_utc": "12:30", "lat": 60.3, "lon": 26.5,
    "vessel_name": "Eagle S", "vessel_flag": "Cook Islands", "vessel_type": "oil_tanker",
    "infrastructure_name": "Estlink 2 + 4 telecom cables", "infrastructure_type": "mixed",
    "region": "Gulf of Finland (off Porvoo)", "attribution_status": "dismissed",
    "narrative": "…", "sources": ["https://…", "https://…"] } ] }
```

---

**Errors:** malformed `bbox` → `422` with `{ "detail": "…" }`; unknown scenario id
→ `404`. **Stub strategy:** the `mock` data source *is* the stub — it serves all
endpoints with the realistic Eagle S scenario; `duckdb` reads real AIS for
`/vessels` and delegates the scoring-dependent endpoints to the mock until the
scoring engine + criticality grid land.
