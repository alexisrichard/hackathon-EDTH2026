# Signal Brick — Handoff to Alexis (from the computer-vision branch)

Generates two kinds of vessel suspicion signals and merges them into a single
table for the scorer.

## What to run
```bash
python scoring/detect_dark_vessels.py --incident INC-2022-09-26
python scoring/detect_dark_vessels.py --incident INC-2024-11-18
python scoring/detect_ais_blackouts.py --incident INC-2024-11-18
python scoring/detect_ais_blackouts.py --incident INC-2022-09-26
python scoring/compile_vessel_signals.py
```
Output: `vessel_signals.csv` + `vessel_signals.json`

## Output schema
| Column | Type | Description |
|---|---|---|
| `incident_id` | str | e.g. `INC-2024-11-18` |
| `vessel_mmsi` | int \| null | null for dark-vessel SAR rows |
| `vessel_name` | str \| null | null for dark-vessel SAR rows |
| `vessel_type` | str \| null | AIS-reported ship type |
| `signal_type` | str | `dark_vessel` \| `ais_blackout` \| `ais_dark_approach` |
| `signal_date_utc` | ISO-8601 | when the signal was observed |
| `lat` / `lon` | float | WGS-84 position |
| `sar_confidence` | float \| null | 0–1 proxy for SAR peak SCR / 15 dB |
| `gap_hours` | float \| null | duration of AIS gap |
| `gap_start_utc` | ISO-8601 \| null | AIS last seen before gap |
| `gap_end_utc` | ISO-8601 \| null | AIS reappeared after gap |
| `details` | str | human-readable description |

### Signal types
- `dark_vessel` (no MMSI): SAR detection with no AIS vessel within 2 km at acquisition time. Identity unknown. → **zone** density, not vessel score.
- `ais_blackout` (MMSI): known vessel had an AIS gap (2–72 h) overlapping the incident window.
- `ais_dark_approach` (MMSI): vessel's first AIS ping in the incident area is within ±24 h of the incident — no prior track. Classic evasion (Yi Peng 3 / C-Lion1).

### Wiring (from handoff)
Rows WITH mmsi → per-vessel score. `weights = {ais_dark_approach: 1.0, ais_blackout: 0.7}`, weight by gap duration.
Rows WITHOUT mmsi (`dark_vessel`) → zone-interest score, aggregate by incident + 0.1° spatial bin.

### Coverage delivered
| Incident | dark_vessel | ais_blackout | ais_dark_approach |
|---|---|---|---|
| INC-2022-09-26 (Nord Stream) | 153 | — | — |
| INC-2024-11-18 (C-Lion1) | 0* | 96 | 176 incl. Yi Peng 3 |

*C-Lion1 SAR scene has poor ship/sea contrast — CFAR finds nothing above threshold.

### Key files
`scoring/detect_dark_vessels.py`, `scoring/detect_ais_blackouts.py`, `scoring/compile_vessel_signals.py`,
`scoring/weights/yolov8n_hrsid_best.pt` (YOLO, mAP50 ~0.91), `detections_nordstream.geojson`,
`ais_blackouts.csv`, **`vessel_signals.csv` (final input)**.
