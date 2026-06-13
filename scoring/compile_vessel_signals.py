"""Compile vessel suspicion signals into a unified table for scoring.

Aggregates two signal sources:
  1. Dark vessels  — SAR detections with no AIS match (from detect_dark_vessels.py)
  2. AIS blackouts — transmission gaps near incident areas (from detect_ais_blackouts.py)

Output: vessel_signals.csv — one row per signal event, ready for Alexis's
suspiciousness scorer to cross with zone-interest scores.

Usage:
  python scoring/compile_vessel_signals.py
  python scoring/compile_vessel_signals.py --dark detections_nordstream.geojson detections_yi_peng3.geojson
  python scoring/compile_vessel_signals.py --blackouts ais_blackouts.csv --out vessel_signals.csv
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

# Minimum confidence to include a dark-vessel SAR detection (proxy: SCR ≥ 14 dB)
DARK_VESSEL_MIN_CONF = 0.93

# Minimum gap to include an AIS blackout (can override with --gap-min-hours)
BLACKOUT_MIN_HOURS = 2.0

# Map GeoJSON filenames to their incident IDs
DETECTION_FILES = {
    "detections_nordstream.geojson": "INC-2022-09-26",
    "detections_yi_peng3.geojson":   "INC-2024-11-18",
}

OUTPUT_FIELDS = [
    "incident_id",
    "vessel_mmsi",
    "vessel_name",
    "vessel_type",
    "signal_type",       # dark_vessel | ais_blackout
    "signal_date_utc",   # ISO-8601 timestamp of signal
    "lat",
    "lon",
    # signal-specific fields (null when not applicable)
    "sar_confidence",    # dark_vessel only: peak_scr / 15 proxy
    "gap_hours",         # ais_blackout only
    "gap_start_utc",     # ais_blackout only
    "gap_end_utc",       # ais_blackout only
    "details",
]


def load_dark_vessel_signals(
    geojson_paths: list[Path],
    min_conf: float,
) -> list[dict]:
    """Load high-confidence dark-vessel SAR detections across incidents."""
    signals = []
    for path in geojson_paths:
        if not path.exists():
            print(f"  SKIP (not found): {path.name}")
            continue

        inc_id = DETECTION_FILES.get(path.name)
        if inc_id is None:
            # Try to infer from filename: detections_<slug>.geojson
            inc_id = "UNKNOWN"

        gdf = gpd.read_file(path)
        dark = gdf[gdf["dark_vessel"] & (gdf["confidence"] >= min_conf)]
        print(f"  {path.name}: {len(dark)} dark-vessel signals (conf ≥ {min_conf})")

        # Infer SAR acquisition date from the detection file name if possible
        # e.g. detections_nordstream → INC-2022-09-26 → 2022-09-29 (scene date)
        scene_date_map = {
            "INC-2022-09-26": "2022-09-29T16:36:54+00:00",
            "INC-2024-11-18": "2024-11-17T16:36:55+00:00",
        }
        signal_date = scene_date_map.get(inc_id, "")

        for _, row in dark.iterrows():
            signals.append({
                "incident_id":    inc_id,
                "vessel_mmsi":    None,
                "vessel_name":    None,
                "vessel_type":    None,
                "signal_type":    "dark_vessel",
                "signal_date_utc": signal_date,
                "lat":            round(row.geometry.y, 5),
                "lon":            round(row.geometry.x, 5),
                "sar_confidence": round(float(row["confidence"]), 3),
                "gap_hours":      None,
                "gap_start_utc":  None,
                "gap_end_utc":    None,
                "details": (
                    f"SAR detection with no AIS vessel within 2 km. "
                    f"Nearest AIS: {row['dist_km']:.1f} km. "
                    f"Peak SCR proxy confidence: {row['confidence']:.2f}."
                ),
            })

    return signals


def load_ais_blackout_signals(
    blackout_path: Path,
    min_gap_hours: float,
) -> list[dict]:
    """Load AIS blackout events from detect_ais_blackouts.py output."""
    if not blackout_path.exists():
        print(f"  SKIP (not found): {blackout_path.name}")
        return []

    df = pd.read_csv(blackout_path)
    # Keep dark-approach rows (gap_hours is NaN) and genuine gaps above threshold
    df = df[(df["signal_type"] == "ais_dark_approach") | (df["gap_hours"] >= min_gap_hours)]
    print(f"  {blackout_path.name}: {len(df)} blackout/approach signals "
          f"({(df['signal_type']=='ais_dark_approach').sum()} dark-approach, "
          f"{(df['signal_type']=='ais_blackout').sum()} gaps ≥ {min_gap_hours}h)")

    signals = []
    for _, row in df.iterrows():
        signals.append({
            "incident_id":    row["incident_id"],
            "vessel_mmsi":    int(row["vessel_mmsi"]) if pd.notna(row["vessel_mmsi"]) else None,
            "vessel_name":    row["vessel_name"] if pd.notna(row["vessel_name"]) else None,
            "vessel_type":    row["vessel_type"] if pd.notna(row["vessel_type"]) else None,
            "signal_type":    row["signal_type"],
            "signal_date_utc": row["gap_start_utc"],
            "lat":            row["gap_midpoint_lat"],
            "lon":            row["gap_midpoint_lon"],
            "sar_confidence": None,
            "gap_hours":      row["gap_hours"],
            "gap_start_utc":  row["gap_start_utc"],
            "gap_end_utc":    row["gap_end_utc"],
            "details": (
                f"Dark approach: vessel first appeared near incident area with no prior track. "
                f"First ping at ({row['last_seen_lat']}, {row['last_seen_lon']})."
            ) if row["signal_type"] == "ais_dark_approach" else (
                f"AIS blackout: {row['gap_hours']:.1f}h gap "
                f"({row['gap_start_utc']} → {row['gap_end_utc']}). "
                f"Last seen at ({row['last_seen_lat']}, {row['last_seen_lon']}), "
                f"reappeared at ({row['reappear_lat']}, {row['reappear_lon']})."
            ),
        })

    return signals


def print_summary(signals: list[dict]):
    by_type = {}
    by_incident = {}
    for s in signals:
        by_type[s["signal_type"]]     = by_type.get(s["signal_type"], 0) + 1
        by_incident[s["incident_id"]] = by_incident.get(s["incident_id"], 0) + 1

    print(f"\n{'═'*60}")
    print(f"Total signals compiled: {len(signals)}")
    print()
    print("By signal type:")
    for k, v in sorted(by_type.items()):
        print(f"  {k:<22} {v:>5}")
    print()
    print("By incident:")
    for k, v in sorted(by_incident.items()):
        print(f"  {k:<28} {v:>5}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dark", nargs="*", default=None,
        help="GeoJSON files from detect_dark_vessels.py (default: auto-discover)",
    )
    parser.add_argument(
        "--blackouts", default="ais_blackouts.csv",
        help="CSV from detect_ais_blackouts.py",
    )
    parser.add_argument(
        "--dark-min-conf", type=float, default=DARK_VESSEL_MIN_CONF,
        help=f"Min SAR confidence for dark vessels (default {DARK_VESSEL_MIN_CONF})",
    )
    parser.add_argument(
        "--gap-min-hours", type=float, default=BLACKOUT_MIN_HOURS,
        help=f"Min gap hours for AIS blackout (default {BLACKOUT_MIN_HOURS})",
    )
    parser.add_argument("--out", default="vessel_signals.csv")
    args = parser.parse_args()

    # Resolve dark-vessel GeoJSON paths
    if args.dark is not None:
        dark_paths = [Path(p) for p in args.dark]
    else:
        # auto-discover known files in repo root
        dark_paths = [ROOT / name for name in DETECTION_FILES]

    print("Loading dark-vessel signals...")
    dark_signals = load_dark_vessel_signals(dark_paths, args.dark_min_conf)

    print("Loading AIS blackout signals...")
    blackout_signals = load_ais_blackout_signals(Path(args.blackouts), args.gap_min_hours)

    signals = dark_signals + blackout_signals

    if not signals:
        print("\nNo signals found. Run detect_dark_vessels.py and detect_ais_blackouts.py first.")
        return

    print_summary(signals)

    out = Path(args.out)
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(signals)
    print(f"\nOutput: {out}  ({len(signals)} rows)")

    # also write JSON for easier downstream parsing
    json_out = out.with_suffix(".json")
    with open(json_out, "w") as f:
        json.dump(signals, f, indent=2, default=str)
    print(f"Output: {json_out}")


if __name__ == "__main__":
    main()
