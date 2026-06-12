# Scoring contract

This document defines the boundary between the scoring engine and the backend.
It is deliberately small so the demo can use either synthetic records or data
prepared by the backend without changing the scoring code.

The scoring engine supports defensive maritime-domain awareness and
infrastructure protection. Its output is a recommendation to collect more
information about an area, not an assessment of intent and not a targeting
recommendation.

## Conventions

- All timestamps are ISO-8601 UTC strings.
- Coordinates are WGS84 (`EPSG:4326`) in `[longitude, latitude]` order.
- Scores and factor values are numbers from `0.0` to `1.0`.
- Distances are kilometres.
- A tasking box is approximately 50 km by 50 km.
- Vessel identifiers are strings so synthetic identifiers and MMSIs both work.
- Missing optional data must reduce confidence, not increase priority.

## Public operations

The Python package will expose two operations:

```python
score_observation(observation: dict) -> dict
rank_tasking(observations: list[dict], top_n: int = 5) -> list[dict]
```

`score_observation` explains the priority associated with one vessel
observation. `rank_tasking` groups observations into 50 km boxes, selects a
compatible satellite window, and returns the highest-priority boxes.

## Input

Each observation has this shape:

```json
{
  "vessel_id": "DEMO-001",
  "vessel_name": "Synthetic Vessel 1",
  "is_synthetic": true,
  "observed_at": "2026-06-12T14:00:00Z",
  "position": [24.75, 59.55],
  "factors": {
    "infrastructure_proximity": 0.90,
    "unusual_movement": 0.70,
    "ais_recency": 0.80,
    "infrastructure_importance": 1.00
  },
  "infrastructure": {
    "id": "DEMO-CABLE-01",
    "name": "Synthetic protected cable",
    "type": "submarine_cable",
    "distance_km": 2.4
  },
  "satellite_windows": [
    {
      "start": "2026-06-12T14:20:00Z",
      "end": "2026-06-12T14:30:00Z",
      "sensor": "SAR",
      "availability": 0.90,
      "is_synthetic": true
    }
  ]
}
```

Required fields:

- `vessel_id`
- `is_synthetic`
- `observed_at`
- `position`
- the four values in `factors`
- `satellite_windows`, which may be an empty list

Optional descriptive fields:

- `vessel_name`
- `infrastructure`

The fifth scoring factor, `satellite_availability`, is obtained from the best
valid entry in `satellite_windows`. It is `0.0` when no valid window exists.

`ais_recency` means confidence that the AIS observation is current: a recent
message receives a high value, while an old or missing message receives a low
value. It is not an "AIS darkness" score. The future weighted rule will use
`1 - ais_recency` for the stale-AIS priority contribution while preserving the
raw value in the explanation.

## Observation output

```json
{
  "vessel_id": "DEMO-001",
  "score": 0.83,
  "confidence": 1.0,
  "factors": {
    "infrastructure_proximity": 0.90,
    "unusual_movement": 0.70,
    "ais_recency": 0.80,
    "infrastructure_importance": 1.00,
    "satellite_availability": 0.90
  },
  "explanation": "High observation priority because the vessel is close to important infrastructure, its movement is unusual, and a SAR window is available soon.",
  "disclaimer": "Defensive collection cue only; this score does not assess hostile intent."
}
```

`confidence` reports input completeness. It is separate from `score`, so
missing information cannot silently look like evidence of elevated priority.

## Ranked tasking output

`rank_tasking` returns at most `top_n` entries:

```json
[
  {
    "rank": 1,
    "grid_id": "demo-grid-24.5-59.5",
    "bbox": [24.50, 59.30, 25.40, 59.75],
    "score": 0.83,
    "recommended_window": {
      "start": "2026-06-12T14:20:00Z",
      "end": "2026-06-12T14:30:00Z",
      "sensor": "SAR"
    },
    "drivers": ["DEMO-001"],
    "explanation": "Priority 1: one synthetic vessel observation near a protected cable, with unusual movement and a compatible SAR window.",
    "is_synthetic": true,
    "disclaimer": "Defensive collection cue only; this recommendation is not for targeting."
  }
]
```

Rules for the ranked output:

- Results are ordered by descending `score`; ties use `grid_id` for stable
  demo output.
- `bbox` is always `[min_lon, min_lat, max_lon, max_lat]`.
- `drivers` contains only the vessel identifiers contributing to that box.
- A box without a valid satellite window is not recommended for immediate
  tasking.
- `recommended_window` is selected from the supplied windows; the scoring
  engine does not claim to predict real satellite orbits.
- `is_synthetic` is true when any driver or window used by the recommendation
  is synthetic or demo-only.

## Validation and failure behaviour

- Reject coordinates outside the Baltic bounding box used by the project.
- Reject malformed timestamps, non-finite numbers, and factor values outside
  `0.0` to `1.0`.
- Reject a satellite window whose end is not after its start.
- Require every satellite window to declare `is_synthetic`.
- Treat a window that ended before `observed_at` as unavailable.
- Treat a window with `availability` equal to `0.0` as unavailable.
- Do not invent missing values.
- Empty input returns an empty ranked list.
- Invalid individual observations produce clear validation errors rather than
  partially trusted recommendations.

## Compatibility with the dashboard API

The backend can map each ranked result directly to `GET /cues` in
`shared/api_contract.md`:

- `bbox` -> `bbox`
- `recommended_window.start` -> `t`
- `recommended_window.sensor` -> `sensor`
- `score` -> `score`
- `drivers` -> `drivers`
- `explanation` -> `why`

No change to `shared/api_contract.md` is required for the first synthetic demo.
