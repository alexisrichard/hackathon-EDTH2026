"""Detect AIS transmission blackouts near Baltic cable incidents.

For each incident, queries all vessels that passed through the area in a ±N-day
window and flags any that had a gap longer than GAP_MIN_HOURS in their AIS
transmission — a known evasion technique for vessels that want to avoid being
tracked near sensitive infrastructure.

Output: ais_blackouts.csv — one row per (MMSI, gap) event.

Usage:
  python scoring/detect_ais_blackouts.py
  python scoring/detect_ais_blackouts.py --incident INC-2024-11-18
  python scoring/detect_ais_blackouts.py --gap-min-hours 4 --out my_blackouts.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timedelta, timezone

from pathlib import Path

import boto3
import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent

GAP_MIN_HOURS      = 2.0   # gaps shorter than this are normal (port comms, VHF shadow)
DAYS_BEFORE        = 5     # look this many days before the incident
DAYS_AFTER         = 2     # and this many days after
AREA_DEG           = 1.0   # half-width of the bounding box around incident centre
INCIDENT_WINDOW_H  = 24    # gap must overlap incident ± this many hours to be flagged


def load_incidents(inc_id: str | None) -> list[dict]:
    rows = []
    with open(ROOT / "data" / "reference" / "incidents.csv") as f:
        for row in csv.DictReader(f):
            if inc_id is None or row["incident_id"] == inc_id:
                rows.append(row)
    if not rows:
        sys.exit(f"Incident '{inc_id}' not found in incidents.csv")
    return rows


def duckdb_con():
    creds = boto3.Session(profile_name="edth2026").get_credentials().get_frozen_credentials()
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET s3_region='eu-west-3'")
    con.execute(f"SET s3_access_key_id='{creds.access_key}'")
    con.execute(f"SET s3_secret_access_key='{creds.secret_key}'")
    if creds.token:
        con.execute(f"SET s3_session_token='{creds.token}'")
    return con


def parquet_paths(start: datetime, end: datetime) -> list[str]:
    paths = []
    cur = start.date()
    while cur <= end.date():
        paths.append(
            f"s3://edth2026-baltic/ais/parquet/source=danish"
            f"/year={cur.year}/month={cur.month:02d}/day={cur.day:02d}/part-0000.parquet"
        )
        cur += timedelta(days=1)
    return paths


def find_blackouts(con, inc: dict, gap_min_hours: float = GAP_MIN_HOURS) -> list[dict]:
    inc_dt = datetime.fromisoformat(f"{inc['date_utc']}T{inc['time_utc'] or '00:00'}:00+00:00")
    lat = float(inc["lat_approx"])
    lon = float(inc["lon_approx"])
    t_from = inc_dt - timedelta(days=DAYS_BEFORE)
    t_to   = inc_dt + timedelta(days=DAYS_AFTER)

    paths = parquet_paths(t_from, t_to)
    # verify at least one path exists before querying
    paths_sql = ", ".join(f"'{p}'" for p in paths)

    print(f"  Querying {len(paths)} days of AIS ({t_from.date()} → {t_to.date()}) "
          f"area {lat:.1f}±{AREA_DEG}°N  {lon:.1f}±{AREA_DEG}°E")

    try:
        df = con.execute(f"""
            SELECT
                MMSI,
                MAX(Name)      AS vessel_name,
                MAX("Ship type") AS ship_type,
                ts,
                Latitude,
                Longitude
            FROM read_parquet([{paths_sql}])
            WHERE Latitude  BETWEEN {lat - AREA_DEG} AND {lat + AREA_DEG}
              AND Longitude BETWEEN {lon - AREA_DEG} AND {lon + AREA_DEG}
              AND MMSI IS NOT NULL
            GROUP BY MMSI, ts, Latitude, Longitude
            ORDER BY MMSI, ts
        """).df()
    except Exception as e:
        print(f"  WARNING: AIS query failed — {e}")
        return []

    if df.empty:
        print("  No AIS data found in area.")
        return []

    n_vessels = df["MMSI"].nunique()
    print(f"  Found {len(df):,} pings from {n_vessels} unique vessels")

    # Incident window for flagging
    inc_t0 = inc_dt - timedelta(hours=INCIDENT_WINDOW_H)
    inc_t1 = inc_dt + timedelta(hours=INCIDENT_WINDOW_H)

    blackouts = []
    for mmsi, track in df.groupby("MMSI"):
        track = track.sort_values("ts").reset_index(drop=True)
        vessel_name = track["vessel_name"].dropna().iloc[-1] if not track["vessel_name"].dropna().empty else None
        ship_type   = track["ship_type"].dropna().iloc[-1]   if not track["ship_type"].dropna().empty   else None

        def ts(i):
            t = pd.Timestamp(track.loc[i, "ts"])
            return t.tz_localize("UTC") if t.tzinfo is None else t

        first_t = ts(0)
        last_t  = ts(len(track) - 1)

        # ── Signal 1: dark approach ──────────────────────────────────────────────
        # Vessel's first ping in the area falls within the incident window.
        # This catches vessels that ran dark while approaching (e.g. Yi Peng 3).
        # We additionally require the vessel had not been present earlier in the
        # query window (first_t is after query_start + 12h = not just a transit).
        query_start_t = t_from.replace(tzinfo=timezone.utc)
        arrived_late  = (first_t - query_start_t).total_seconds() / 3600 > 12
        if inc_t0 <= first_t <= inc_t1 and arrived_late:
            blackouts.append({
                "incident_id":      inc["incident_id"],
                "vessel_mmsi":      int(mmsi),
                "vessel_name":      vessel_name,
                "vessel_type":      ship_type,
                "signal_type":      "ais_dark_approach",
                "gap_start_utc":    None,
                "gap_end_utc":      None,
                "gap_hours":        None,
                "last_seen_lat":    round(float(track.loc[0, "Latitude"]),  5),
                "last_seen_lon":    round(float(track.loc[0, "Longitude"]), 5),
                "reappear_lat":     round(float(track.loc[0, "Latitude"]),  5),
                "reappear_lon":     round(float(track.loc[0, "Longitude"]), 5),
                "gap_midpoint_lat": round(float(track.loc[0, "Latitude"]),  5),
                "gap_midpoint_lon": round(float(track.loc[0, "Longitude"]), 5),
            })

        # ── Signal 2: AIS gap overlapping the incident window ────────────────────
        # Look for transmission gaps within the track that coincide with the
        # incident time AND are shorter than MAX_GAP_H (avoids transit noise
        # from vessels that just passed through the Danish AIS footprint once).
        MAX_GAP_H = 72  # gaps longer than this = vessel simply left AIS range
        for i in range(len(track) - 1):
            t0 = ts(i)
            t1 = ts(i + 1)
            gap_h = (t1 - t0).total_seconds() / 3600.0

            gap_overlaps = (t0 <= inc_t1) and (t1 >= inc_t0)
            if gap_min_hours <= gap_h <= MAX_GAP_H and gap_overlaps:
                mid_lat = (track.loc[i, "Latitude"]  + track.loc[i+1, "Latitude"])  / 2
                mid_lon = (track.loc[i, "Longitude"] + track.loc[i+1, "Longitude"]) / 2
                blackouts.append({
                    "incident_id":      inc["incident_id"],
                    "vessel_mmsi":      int(mmsi),
                    "vessel_name":      vessel_name,
                    "vessel_type":      ship_type,
                    "signal_type":      "ais_blackout",
                    "gap_start_utc":    t0.isoformat(),
                    "gap_end_utc":      t1.isoformat(),
                    "gap_hours":        round(gap_h, 2),
                    "last_seen_lat":    round(float(track.loc[i,   "Latitude"]),  5),
                    "last_seen_lon":    round(float(track.loc[i,   "Longitude"]), 5),
                    "reappear_lat":     round(float(track.loc[i+1, "Latitude"]),  5),
                    "reappear_lon":     round(float(track.loc[i+1, "Longitude"]), 5),
                    "gap_midpoint_lat": round(mid_lat, 5),
                    "gap_midpoint_lon": round(mid_lon, 5),
                })

    return blackouts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--incident",      default=None, help="e.g. INC-2024-11-18 (default: all)")
    parser.add_argument("--gap-min-hours", type=float, default=GAP_MIN_HOURS)
    parser.add_argument("--out",           default="ais_blackouts.csv")
    args = parser.parse_args()

    incidents = load_incidents(args.incident)
    con = duckdb_con()

    all_blackouts: list[dict] = []
    for inc in incidents:
        print(f"\n{'─'*60}")
        print(f"Incident : {inc['incident_id']} — {inc['name']}")
        results = find_blackouts(con, inc, args.gap_min_hours)
        all_blackouts.extend(results)
        print(f"  Blackouts found (gap ≥ {args.gap_min_hours}h): {len(results)}")
        if results:
            # summarise top offenders
            by_vessel = {}
            for r in results:
                k = (r["vessel_mmsi"], r["vessel_name"])
                by_vessel.setdefault(k, []).append(r["gap_hours"] or 0)
            for (mmsi, name), gaps in sorted(by_vessel.items(), key=lambda x: -max(x[1])):
                print(f"    MMSI {mmsi:>12}  {str(name):<28}  "
                      f"n_gaps={len(gaps)}  max={max(gaps):.1f}h  total={sum(gaps):.1f}h")

    if not all_blackouts:
        print("\nNo blackouts found.")
        return

    out = Path(args.out)
    fieldnames = [
        "incident_id", "vessel_mmsi", "vessel_name", "vessel_type",
        "signal_type", "gap_start_utc", "gap_end_utc", "gap_hours",
        "last_seen_lat", "last_seen_lon", "reappear_lat", "reappear_lon",
        "gap_midpoint_lat", "gap_midpoint_lon",
    ]
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_blackouts)

    print(f"\n{'═'*60}")
    print(f"Total blackout events : {len(all_blackouts)}")
    print(f"Output                : {out}")


if __name__ == "__main__":
    main()
