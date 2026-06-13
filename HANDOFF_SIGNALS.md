# Signal Brick — Handoff to Alexis

Built by the computer-vision branch. Generates two kinds of vessel suspicion
signals and merges them into a single table for your scorer.

---

## What to run

```bash
# 1. SAR dark-vessel detection (per incident)
python scoring/detect_dark_vessels.py --incident INC-2022-09-26
python scoring/detect_dark_vessels.py --incident INC-2024-11-18

# 2. AIS anomaly detection (per incident)
python scoring/detect_ais_blackouts.py --incident INC-2024-11-18
python scoring/detect_ais_blackouts.py --incident INC-2022-09-26

# 3. Compile everything into the signal table
python scoring/compile_vessel_signals.py
```

Output: `vessel_signals.csv` + `vessel_signals.json`

---

## Output schema

| Column | Type | Description |
|---|---|---|
| `incident_id` | str | e.g. `INC-2024-11-18` |
| `vessel_mmsi` | int \| null | null for dark-vessel SAR rows |
| `vessel_name` | str \| null | null for dark-vessel SAR rows |
| `vessel_type` | str \| null | AIS-reported ship type |
| `signal_type` | str | see below |
| `signal_date_utc` | ISO-8601 | when the signal was observed |
| `lat` / `lon` | float | WGS-84 position |
| `sar_confidence` | float \| null | 0–1 proxy for SAR peak SCR / 15 dB |
| `gap_hours` | float \| null | duration of AIS gap |
| `gap_start_utc` | ISO-8601 \| null | AIS last seen before gap |
| `gap_end_utc` | ISO-8601 \| null | AIS reappeared after gap |
| `details` | str | human-readable description |

### Signal types

| `signal_type` | MMSI present? | Meaning |
|---|---|---|
| `dark_vessel` | ❌ | SAR detection with no AIS vessel within 2 km at acquisition time. Identity unknown. |
| `ais_blackout` | ✅ | Known vessel had an AIS transmission gap (2–72 h) that overlaps the incident time window. |
| `ais_dark_approach` | ✅ | Known vessel's first AIS ping in the incident area falls within ±24 h of the incident — no prior track visible. Classic evasion pattern (Yi Peng 3 for C-Lion1). |

---

## How to wire into your scorer

**Rows WITH mmsi** → per-vessel suspiciousness score.
Weight by signal type and gap duration. Example:

```python
weights = {
    "ais_dark_approach": 1.0,   # strongest: no approach track at all
    "ais_blackout":      0.7,   # intentional gap overlapping incident
}
score = sum(weights[s["signal_type"]] * gap_factor(s) for s in vessel_signals)
```

**Rows WITHOUT mmsi** (`dark_vessel`) → zone anomaly density.
These feed your zone-interest score, not the vessel score.
Aggregate by incident + spatial bin (e.g. 0.1° grid):

```python
zone_density = dark_vessel_df.groupby(
    [pd.cut(df.lat, bins), pd.cut(df.lon, bins)]
).size()
```

---

## Current coverage

| Incident | dark_vessel | ais_blackout | ais_dark_approach |
|---|---|---|---|
| INC-2022-09-26 (Nord Stream) | 153 | — | — |
| INC-2024-11-18 (C-Lion1) | 0* | 96 | 176 incl. Yi Peng 3 |

*C-Lion1 SAR scene has poor ship/sea contrast — CFAR finds nothing above threshold.

---

## Key files

| File | Purpose |
|---|---|
| `scoring/detect_dark_vessels.py` | SAR CFAR pipeline → `detections_{slug}.geojson` |
| `scoring/detect_ais_blackouts.py` | AIS gap/approach detector → `ais_blackouts.csv` |
| `scoring/compile_vessel_signals.py` | Merges both → `vessel_signals.csv` / `.json` |
| `scoring/weights/yolov8n_hrsid_best.pt` | YOLO model (Alexis trained, 50 ep, mAP50 ~0.91) |
| `detections_nordstream.geojson` | Raw SAR detections for Nord Stream |
| `ais_blackouts.csv` | Raw AIS anomalies |
| `vessel_signals.csv` | **Final signal table — this is your input** |
