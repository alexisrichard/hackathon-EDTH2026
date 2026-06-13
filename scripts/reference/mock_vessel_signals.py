"""Mock `vessel_signals.csv` matching the Signal Brick handoff schema + coverage.

The computer-vision branch's real `vessel_signals.csv` isn't merged yet. This
generates a representative stand-in so the scorer, zone engine, and webapp can be
built and demoed end-to-end now; swap the real file in when it lands (same schema,
same path resolution in scoring/sar_signals.py).

Coverage mirrors the handoff:
  INC-2022-09-26 (Nord Stream): 153 dark_vessel (no MMSI) around the blast site.
  INC-2024-11-18 (C-Lion1):     96 ais_blackout + 176 ais_dark_approach incl
                                Yi Peng 3 (MMSI 414270000).
Real MMSIs are sampled from the stitched cut-day tile so per-vessel joins work.
Deterministic (seeded).
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TILES = ROOT / "frontend/public/data/ais_v2"
OUT_CSV = ROOT / "data/reference/vessel_signals.mock.csv"
OUT_JSON = ROOT / "data/reference/vessel_signals.mock.json"

COLS = ["incident_id", "vessel_mmsi", "vessel_name", "vessel_type", "signal_type",
        "signal_date_utc", "lat", "lon", "sar_confidence", "gap_hours",
        "gap_start_utc", "gap_end_utc", "details"]

YI_PENG_3 = 414270000
CLION1 = {"lat": 55.30, "lon": 16.10}      # C-Lion1 / BCS corridor near Bornholm
NORDSTREAM = {"lat": 55.50, "lon": 15.40}  # NS blast site NE of Bornholm


def _vessels_near(tile_path: Path, lon_rng, lat_rng, types):
    out = []
    if not tile_path.exists():
        return out
    for v in json.load(open(tile_path))["vessels"]:
        if not v["kf"] or v["type"] not in types:
            continue
        # any keyframe inside the box (a transit passes through, not just its seam)
        hit = next(
            (k for k in v["kf"]
             if lon_rng[0] <= k[1] <= lon_rng[1] and lat_rng[0] <= k[2] <= lat_rng[1]),
            None,
        )
        if hit:
            out.append((v["mmsi"], v.get("name"), v["type"], hit[1], hit[2]))
    return out


def main():
    rnd = random.Random(42)
    rows = []

    # ---- C-Lion1: dark approaches + blackouts on real TRANSIT-class MMSIs ----
    # Restrict to cargo/tanker: a "dark approach" (no prior track, evasion pattern)
    # belongs on a transiting merchant vessel, not a local pilot/rescue/survey boat
    # (those are 'other' near Bornholm and would otherwise dominate the headline).
    pool = _vessels_near(TILES / "tracks_2024-11-18.json", (12.0, 22.0), (53.5, 60.0),
                         {"cargo", "tanker", "passenger"})
    rnd.shuffle(pool)
    # Hero first, explicit.
    rows.append(dict(incident_id="INC-2024-11-18", vessel_mmsi=YI_PENG_3,
                     vessel_name="Yi Peng 3", vessel_type="cargo",
                     signal_type="ais_dark_approach", signal_date_utc="2024-11-17T12:00:00Z",
                     lat=55.10, lon=15.80, sar_confidence="", gap_hours="",
                     gap_start_utc="", gap_end_utc="",
                     details="First AIS appearance near the corridor with no prior Baltic track"))
    others = [v for v in pool if v[0] != YI_PENG_3]
    split = max(1, len(others) // 2)  # split the transit pool: dark approaches + blackouts
    approach = others[:split]
    for i, (mmsi, name, typ, lo, la) in enumerate(approach):
        day = 10 + (i % 9)  # 11-10 .. 11-18
        rows.append(dict(incident_id="INC-2024-11-18", vessel_mmsi=mmsi, vessel_name=name,
                         vessel_type=typ, signal_type="ais_dark_approach",
                         signal_date_utc=f"2024-11-{day:02d}T{6 + i % 12:02d}:00:00Z",
                         lat=round(la, 4), lon=round(lo, 4), sar_confidence="", gap_hours="",
                         gap_start_utc="", gap_end_utc="",
                         details="No prior track in coverage before first incident-area ping"))
    black = others[split:split + 96]
    for i, (mmsi, name, typ, lo, la) in enumerate(black):
        gh = round(2 + rnd.random() * 70, 1)
        rows.append(dict(incident_id="INC-2024-11-18", vessel_mmsi=mmsi, vessel_name=name,
                         vessel_type=typ, signal_type="ais_blackout",
                         signal_date_utc="2024-11-18T02:00:00Z",
                         lat=round(la, 4), lon=round(lo, 4), sar_confidence="", gap_hours=gh,
                         gap_start_utc="2024-11-17T22:00:00Z", gap_end_utc="2024-11-18T10:00:00Z",
                         details=f"AIS gap {gh} h overlapping the incident window"))

    # ---- Nord Stream: 153 dark-vessel SAR detections (no MMSI) around blast ----
    for i in range(153):
        la = NORDSTREAM["lat"] + rnd.uniform(-0.35, 0.35)
        lo = NORDSTREAM["lon"] + rnd.uniform(-0.5, 0.5)
        rows.append(dict(incident_id="INC-2022-09-26", vessel_mmsi="", vessel_name="",
                         vessel_type="", signal_type="dark_vessel",
                         signal_date_utc="2022-09-26T05:00:00Z",
                         lat=round(la, 4), lon=round(lo, 4),
                         sar_confidence=round(0.4 + rnd.random() * 0.6, 3),
                         gap_hours="", gap_start_utc="", gap_end_utc="",
                         details="SAR detection, no AIS vessel within 2 km at acquisition"))

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)
    json.dump(rows, open(OUT_JSON, "w"), indent=1)
    by = {}
    for r in rows:
        by[(r["incident_id"], r["signal_type"])] = by.get((r["incident_id"], r["signal_type"]), 0) + 1
    print(f"wrote {len(rows)} rows -> {OUT_CSV.relative_to(ROOT)}")
    for k, n in sorted(by.items()):
        print(f"  {k[0]} {k[1]}: {n}")


if __name__ == "__main__":
    main()
