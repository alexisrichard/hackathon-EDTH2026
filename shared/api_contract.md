# API contract — backend ↔ frontend

**Source of truth for the JSON shapes the dashboard consumes.** Draft below — **finalize together Friday**, then change only via PR + a heads-up (the frontend mocks against this; a silent change breaks it).

Base URL: `http://localhost:8000` (dev). All times ISO-8601 UTC. All coords `[lon, lat]` (EPSG:4326).

---

### `GET /vessels?bbox=&start=&end=`
Vessel tracks in a bbox + time window (replayed from AIS parquet).
```jsonc
{ "vessels": [
  { "mmsi": 123456789, "name": "EAGLE S", "ship_type": "Tanker",
    "track": [ { "t": "2024-12-25T14:00:00Z", "lon": 26.1, "lat": 60.0, "sog": 2.1, "cog": 92 } ] }
] }
```

### `GET /scores?bbox=&t=`
Per-vessel suspicion at time `t`, with the interpretable breakdown.
```jsonc
{ "scores": [
  { "mmsi": 123456789, "score": 0.87,
    "terms": { "kinematic_anomaly": 0.6, "class_coherence": 0.12, "local_criticality": 0.91, "dark_modifier": 1.0 },
    "why": "declared tanker, slowed to 2kn over Estlink 2, AIS gap 47 min" } ] }
```

### `GET /cues?t=&top=5`
Top-N areas to task next (the product).
```jsonc
{ "cues": [
  { "rank": 1, "bbox": [25.9, 59.9, 26.3, 60.2], "t": "2024-12-25T14:00:00Z",
    "sensor": "SAR", "score": 0.93, "drivers": [123456789], "why": "…" } ] }
```

### `GET /scenarios`
Named incident replays for the demo (mirrors `shared/scenarios.json`).
```jsonc
{ "scenarios": [
  { "id": "eagle-s-2024-12-25", "name": "Eagle S / Estlink 2",
    "start": "2024-12-25T00:00:00Z", "end": "2024-12-26T00:00:00Z",
    "bbox": [25, 59, 28, 61], "suspect_mmsi": 123456789 } ] }
```

---

**Stub strategy:** backend can serve these from fixtures/random data first so the frontend is never blocked; swap in real DuckDB-backed responses as they land.
