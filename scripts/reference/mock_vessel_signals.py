"""Mock `vessel_signals.csv` matching the Signal Brick handoff schema + coverage.

The computer-vision branch's real `vessel_signals.csv` isn't merged yet. This
generates a representative stand-in so the scorer, zone engine, and webapp can be
built and demoed end-to-end now; swap the real file in when it lands (same schema,
same path resolution in scoring/sar_signals.py).

Coverage approximates the handoff. The handoff's per-vessel counts (Nord Stream
153 dark_vessel; C-Lion1 ~96 blackout + ~176 dark_approach) are detection-event
upper bounds; this mock emits the DISTINCT vessels that faithfully match each
signal's definition, gated by how many real corridor MMSIs qualify:
  INC-2022-09-26 (Nord Stream): 153 dark_vessel (no MMSI) around the blast site.
  INC-2024-11-18 (C-Lion1):     a handful of ais_dark_approach (only vessels with
                                ~no prior Baltic track, incl. Yi Peng 3 414270000)
                                + ais_blackout (only established tracks with a gap).
Real MMSIs are sampled from the stitched cut-day tile so per-vessel joins work.
Deterministic (seeded). Run prints the exact emitted counts.
"""
from __future__ import annotations

import csv
import glob
import json
import os
import random
from collections import Counter
from datetime import date, timedelta
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
            has_gap = bool(v.get("gaps"))
            out.append((v["mmsi"], v.get("name"), v["type"], hit[1], hit[2], has_gap))
    return out


def _prior_day_counts(mmsis, cut: str, lookback: int = 90):
    """How many day-tiles in the lookback window each MMSI appears in. This is the
    signal's own discriminator: a 'dark approach' (no prior track) is only honest
    on a vessel with ~0 prior days; a 'blackout' presupposes an established track."""
    targets = set(mmsis)
    start = (date.fromisoformat(cut) - timedelta(days=lookback)).isoformat()
    counts: Counter = Counter()
    for f in sorted(glob.glob(str(TILES / "tracks_*.json"))):
        d = os.path.basename(f)[len("tracks_") : -len(".json")]
        if d < start or d >= cut:
            continue
        for v in json.load(open(f))["vessels"]:
            if v["mmsi"] in targets:
                counts[v["mmsi"]] += 1
    return counts


def main():
    rnd = random.Random(42)
    rows = []

    # ---- C-Lion1: dark approaches + blackouts on real TRANSIT-class MMSIs ----
    # Restrict to cargo/tanker/passenger (a transiting merchant, not a local
    # pilot/rescue/survey 'other' boat near Bornholm), THEN make each signal
    # faithful to its own definition using prior-track richness:
    #   ais_dark_approach -> only vessels with ~no prior Baltic track (the signal
    #                        literally means "appeared from nowhere"). A daily
    #                        ferry has 30+ prior days and can never qualify.
    #   ais_blackout      -> only established tracks (prior days) that actually
    #                        carry an AIS gap on the cut-day tile.
    # This keeps the hero's dark-approach distinctive instead of spraying it on
    # ferries — overfit-free, because it's the signal's own semantics, not tuning.
    pool = _vessels_near(TILES / "tracks_2024-11-18.json", (12.0, 22.0), (53.5, 60.0),
                         {"cargo", "tanker", "passenger"})
    pdays = _prior_day_counts({v[0] for v in pool}, cut="2024-11-18")
    # Hero first, explicit (genuinely 0 prior Baltic days in our window).
    rows.append(dict(incident_id="INC-2024-11-18", vessel_mmsi=YI_PENG_3,
                     vessel_name="Yi Peng 3", vessel_type="cargo",
                     signal_type="ais_dark_approach", signal_date_utc="2024-11-17T12:00:00Z",
                     lat=55.10, lon=15.80, sar_confidence="", gap_hours="",
                     gap_start_utc="", gap_end_utc="",
                     details="First AIS appearance near the corridor with no prior Baltic track"))
    others = [v for v in pool if v[0] != YI_PENG_3]
    no_track = [v for v in others if pdays.get(v[0], 0) <= 3]       # appeared from nowhere
    established_gap = [v for v in others if pdays.get(v[0], 0) >= 10 and v[5]]  # had track, went dark
    rnd.shuffle(no_track)
    rnd.shuffle(established_gap)
    for i, (mmsi, name, typ, lo, la, _g) in enumerate(no_track):
        day = 10 + (i % 9)  # 11-10 .. 11-18
        rows.append(dict(incident_id="INC-2024-11-18", vessel_mmsi=mmsi, vessel_name=name,
                         vessel_type=typ, signal_type="ais_dark_approach",
                         signal_date_utc=f"2024-11-{day:02d}T{6 + i % 12:02d}:00:00Z",
                         lat=round(la, 4), lon=round(lo, 4), sar_confidence="", gap_hours="",
                         gap_start_utc="", gap_end_utc="",
                         details="No prior track in coverage before first incident-area ping"))
    for i, (mmsi, name, typ, lo, la, _g) in enumerate(established_gap[:96]):
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
