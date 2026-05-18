"""Identify suspicious vessel behavior: slow movement over high-criticality cells.

For a given date, this script:
  1. Loads Danish AIS for the date from S3
  2. Loads the criticality grid from data/geo/criticality_grid.npz
  3. For each AIS point, looks up the criticality score at that cell
  4. Flags vessels that spent N+ minutes at SOG < 4 knots in cells with score > 0.5
     while not in port (i.e. not in a port-criticality dominated cell)
  5. Outputs vessel-level suspicious-behavior summary

This is the MVP of the §5.4 PLAN suspicion engine. It catches "anchor drag near
cable" behavior — the pattern that links Eagle S, Newnew Polar Bear, Yi Peng 3,
and Fitburg.

Usage:
  python scripts/analysis/suspicious_behavior.py 2024-12-25
  python scripts/analysis/suspicious_behavior.py 2024-11-17 2024-11-18
"""
from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.duck import connect  # type: ignore


GRID_PATH = Path("data/geo/criticality_grid.npz")
OUT_DIR = Path("data/reference")


def load_grid() -> dict:
    """Load the criticality grid + components."""
    npz = np.load(GRID_PATH, allow_pickle=True)
    return {
        "score": npz["score"],
        "lats": npz["lats"],
        "lons": npz["lons"],
        "cables_score": npz.get("score_cables") if "score_cables" in npz.files else None,
        "ports_score": npz.get("score_ports") if "score_ports" in npz.files else None,
    }


def grid_lookup(df: pd.DataFrame, grid: dict) -> pd.DataFrame:
    """Add criticality columns to a DataFrame with Latitude/Longitude."""
    lats, lons = grid["lats"], grid["lons"]
    score = grid["score"]
    cables_score = grid["cables_score"]
    ports_score = grid["ports_score"]

    # Bucket lat/lon to grid indices
    cell_deg = lats[1] - lats[0]
    i = np.clip(((df["Latitude"].values - lats[0]) / cell_deg).astype(int), 0, len(lats) - 1)
    j = np.clip(((df["Longitude"].values - lons[0]) / cell_deg).astype(int), 0, len(lons) - 1)
    df = df.copy()
    df["crit_score"] = score[i, j]
    if cables_score is not None:
        df["crit_cables"] = cables_score[i, j]
    if ports_score is not None:
        df["crit_ports"] = ports_score[i, j]
    return df


def analyse_day(d: date, grid: dict) -> pd.DataFrame:
    glob = f"s3://edth2026-baltic/ais/parquet/source=danish/year={d.year}/month={d.month:02d}/day={d.day:02d}/part-*.parquet"
    con = connect()
    try:
        # Check existence
        exists = con.execute(f"SELECT COUNT(*) FROM read_parquet('{glob}')").fetchone()[0]
    except Exception:
        exists = 0
    if not exists:
        print(f"  {d}: no AIS in S3", flush=True)
        con.close()
        return pd.DataFrame()
    print(f"  {d}: loading AIS ({exists:,} rows)", flush=True)

    # Stream into pandas in chunks via DuckDB
    df = con.execute(f"""
    SELECT MMSI, Name, \"Ship type\", IMO, Latitude, Longitude, SOG, COG, Heading, ts
    FROM read_parquet('{glob}')
    WHERE SOG IS NOT NULL AND SOG < 4 AND SOG >= 0.1
      AND Latitude BETWEEN 52 AND 66 AND Longitude BETWEEN 9 AND 30
    """).df()
    con.close()
    print(f"  {d}: {len(df):,} slow-vessel points (SOG 0.1-4 kn)", flush=True)

    df = grid_lookup(df, grid)

    # Filter: high non-port criticality
    # crit_ports could be high simply because vessel is in port — exclude those
    if "crit_ports" in df.columns:
        df["crit_non_port"] = df["crit_score"] - df["crit_ports"] * 0.5
        suspicious = df[(df["crit_score"] > 0.5) & (df["crit_ports"] < 0.5)]
    else:
        suspicious = df[df["crit_score"] > 0.5]
    print(f"  {d}: {len(suspicious):,} suspicious points after port-filter", flush=True)

    # Aggregate per vessel
    agg = suspicious.groupby("MMSI").agg(
        Name=("Name", lambda x: x.dropna().iloc[0] if x.dropna().size else ""),
        ship_type=("Ship type", lambda x: x.dropna().iloc[0] if x.dropna().size else ""),
        IMO=("IMO", lambda x: x.dropna().iloc[0] if x.dropna().size else None),
        n_suspicious_points=("crit_score", "size"),
        avg_crit=("crit_score", "mean"),
        max_crit=("crit_score", "max"),
        min_sog=("SOG", "min"),
        avg_sog=("SOG", "mean"),
        first_seen=("ts", "min"),
        last_seen=("ts", "max"),
    ).reset_index()
    # Duration in minutes (approx: count * 1 minute, since Danish AIS is dense)
    # Actually use ts range
    agg["duration_minutes"] = (agg["last_seen"] - agg["first_seen"]).dt.total_seconds() / 60
    agg["date_utc"] = d.isoformat()
    return agg


def main(argv: list[str]) -> int:
    if not GRID_PATH.exists():
        print(f"ERROR: criticality grid not found at {GRID_PATH}. Run scripts/geo/build_criticality_raster.py first.",
              file=sys.stderr)
        return 1
    grid = load_grid()
    print(f"Grid loaded: shape={grid['score'].shape}", flush=True)

    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2

    out_rows: list[pd.DataFrame] = []
    for arg in argv[1:]:
        d = datetime.fromisoformat(arg).date()
        df = analyse_day(d, grid)
        if not df.empty:
            out_rows.append(df)

    if not out_rows:
        print("\nNo suspicious behavior detected (or no data for given dates).", flush=True)
        return 0

    all_df = pd.concat(out_rows, ignore_index=True).sort_values(["date_utc", "max_crit"], ascending=[True, False])
    out_path = OUT_DIR / "suspicious_behavior.csv"
    all_df.to_csv(out_path, index=False)
    print(f"\nWrote {len(all_df)} vessel-day rows -> {out_path}", flush=True)

    # Top 15 per day
    print("\n=== TOP suspicious vessels per day ===", flush=True)
    for d_str, group in all_df.groupby("date_utc"):
        print(f"\n[{d_str}] top 10 by max_crit:")
        cols = ["MMSI", "Name", "ship_type", "n_suspicious_points",
                "max_crit", "min_sog", "duration_minutes"]
        print(group.nlargest(10, "max_crit")[cols].to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
