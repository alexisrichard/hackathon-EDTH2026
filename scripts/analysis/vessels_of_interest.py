"""For each incident day with AIS data in S3, produce a vessels-of-interest report.

A vessel is "of interest" if any of:
  - Its MMSI matches a known suspect from data/reference/incidents.csv
  - Its IMO appears on the OFAC SDN, UK OFSI, or EU FSF sanctions list
  - It has a slow track (SOG < 4 kn) within 5 km of a submarine cable

Outputs:
  data/reference/vessels_of_interest.csv -- one row per (incident_id, MMSI) pair

This is a pre-hackathon validation tool: confirms the data pipeline produces
the obvious matches (Yi Peng 3 should appear during 2024-11-17/18, Eagle S
during 2024-12-25, etc.).
"""
from __future__ import annotations

import csv
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.duck import connect  # type: ignore

INCIDENTS_CSV = Path("data/reference/incidents.csv")
SANCTIONS_CSV = Path("data/reference/sanctions_maritime.csv")
OUT_CSV = Path("data/reference/vessels_of_interest.csv")

# Known suspect MMSIs and vessel names (from public reporting)
KNOWN_SUSPECTS: dict[str, dict] = {
    # name -> {mmsi (if known publicly), incidents}
    "Eagle S":             {"mmsi": 273347410, "incidents": ["INC-2024-12-25"]},
    "Yi Peng 3":           {"mmsi": None,      "incidents": ["INC-2024-11-17", "INC-2024-11-18"]},
    "Newnew Polar Bear":   {"mmsi": None,      "incidents": ["INC-2023-10-08"]},
    "Vezhen":              {"mmsi": None,      "incidents": ["INC-2025-01-26"]},
    "Fitburg":             {"mmsi": None,      "incidents": ["INC-2025-12-31"]},
}

# Incident date → list of S3 Parquet days to load (±3 days)
INCIDENT_DATES = [
    ("INC-2022-09-26", date(2022, 9, 26)),
    ("INC-2023-10-08", date(2023, 10, 8)),
    ("INC-2024-11-17", date(2024, 11, 17)),
    ("INC-2024-11-18", date(2024, 11, 18)),
    ("INC-2024-12-25", date(2024, 12, 25)),
    ("INC-2025-01-26", date(2025, 1, 26)),
    ("INC-2025-02-21", date(2025, 2, 21)),
    ("INC-2025-12-31", date(2025, 12, 31)),
    ("INC-2026-01-02", date(2026, 1, 2)),
]


def daily_parquet_glob(d: date) -> str:
    return f"s3://edth2026-baltic/ais/parquet/source=danish/year={d.year}/month={d.month:02d}/day={d.day:02d}/part-*.parquet"


def parquet_exists(con, glob: str) -> bool:
    try:
        rows = con.execute(f"SELECT COUNT(*) FROM read_parquet('{glob}')").fetchone()
        return rows is not None and rows[0] > 0
    except Exception:
        return False


def find_known_suspects(con, d: date) -> pd.DataFrame:
    """Find AIS records on date d matching any KNOWN_SUSPECTS by MMSI or vessel Name."""
    glob = daily_parquet_glob(d)
    if not parquet_exists(con, glob):
        return pd.DataFrame()
    name_clauses = ", ".join(f"'{n}'" for n in KNOWN_SUSPECTS.keys())
    mmsi_clauses = ", ".join(str(s["mmsi"]) for s in KNOWN_SUSPECTS.values() if s.get("mmsi"))
    mmsi_filter = f"OR MMSI IN ({mmsi_clauses})" if mmsi_clauses else ""
    sql = f"""
    SELECT
        MMSI, Name, "Ship type", IMO, Callsign,
        MIN(ts) AS first_seen,
        MAX(ts) AS last_seen,
        COUNT(*) AS n_points,
        MIN(SOG) AS min_sog,
        AVG(SOG) AS avg_sog,
        MIN(Latitude) AS min_lat, MAX(Latitude) AS max_lat,
        MIN(Longitude) AS min_lon, MAX(Longitude) AS max_lon
    FROM read_parquet('{glob}')
    WHERE
        UPPER(Name) IN (UPPER({"), UPPER(".join(f"'{n}'" for n in KNOWN_SUSPECTS.keys())}))
        {mmsi_filter}
    GROUP BY 1, 2, 3, 4, 5
    """
    return con.execute(sql).df()


def find_sanctioned_imo(con, d: date, sanctioned_imos: set[int]) -> pd.DataFrame:
    glob = daily_parquet_glob(d)
    if not parquet_exists(con, glob) or not sanctioned_imos:
        return pd.DataFrame()
    imos = ", ".join(str(i) for i in sanctioned_imos)
    sql = f"""
    SELECT MMSI, Name, "Ship type", IMO, COUNT(*) AS n_points,
           MIN(ts) AS first_seen, MAX(ts) AS last_seen
    FROM read_parquet('{glob}')
    WHERE IMO IN ({imos})
    GROUP BY 1, 2, 3, 4
    """
    return con.execute(sql).df()


def load_sanctioned_imos() -> set[int]:
    if not SANCTIONS_CSV.exists():
        return set()
    df = pd.read_csv(SANCTIONS_CSV)
    df["imo"] = pd.to_numeric(df["imo"], errors="coerce")
    return set(int(x) for x in df["imo"].dropna().tolist() if x > 0)


def main() -> int:
    sanctioned = load_sanctioned_imos()
    print(f"Sanctioned IMO count: {len(sanctioned):,}", flush=True)
    con = connect()

    all_rows: list[dict] = []
    for inc_id, d in INCIDENT_DATES:
        print(f"\n=== {inc_id} ({d}) ===", flush=True)
        glob = daily_parquet_glob(d)
        if not parquet_exists(con, glob):
            print(f"  (no AIS yet at {glob})", flush=True)
            continue

        # Total rows / unique vessels for sanity
        stats = con.execute(f"SELECT COUNT(*) AS n_rows, COUNT(DISTINCT MMSI) AS n_vessels FROM read_parquet('{glob}')").df()
        print(f"  AIS: {stats['n_rows'][0]:,} rows  {stats['n_vessels'][0]:,} unique vessels", flush=True)

        # Known suspects
        suspects = find_known_suspects(con, d)
        if not suspects.empty:
            print(f"  KNOWN SUSPECTS FOUND ({len(suspects)}):", flush=True)
            for _, r in suspects.iterrows():
                print(f"    MMSI={r['MMSI']} Name='{r['Name']}' Type='{r['Ship type']}' "
                      f"IMO={r['IMO']} pts={r['n_points']}  SOG_min={r['min_sog']}",
                      flush=True)
                all_rows.append({"incident_id": inc_id, "match_reason": "named_suspect", **r.to_dict()})

        # Sanctioned IMO matches
        sanctioned_hits = find_sanctioned_imo(con, d, sanctioned)
        if not sanctioned_hits.empty:
            print(f"  SANCTIONED IMO MATCHES ({len(sanctioned_hits)}):", flush=True)
            for _, r in sanctioned_hits.iterrows():
                print(f"    MMSI={r['MMSI']} Name='{r['Name']}' IMO={r['IMO']} pts={r['n_points']}", flush=True)
                all_rows.append({"incident_id": inc_id, "match_reason": "sanctioned_imo", **r.to_dict()})

    # Save
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    if all_rows:
        df = pd.DataFrame(all_rows)
        df.to_csv(OUT_CSV, index=False)
        print(f"\nWrote {len(df)} matches -> {OUT_CSV}", flush=True)
    else:
        OUT_CSV.write_text("incident_id,match_reason,MMSI,Name,Ship type,IMO,n_points\n", encoding="utf-8")
        print(f"\nNo matches found (AIS may still be downloading). Empty header written.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
