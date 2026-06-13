"""Build compact replay track tiles from the AIS archive on S3.

Reads one day of Danish AIS parquet via DuckDB-over-S3, thins to ~1 ping per
vessel per 30 s, simplifies each vessel's trajectory with Douglas-Peucker
(~150 m), detects AIS gaps, and writes a compact keyframe tile the web app
replays by interpolating between keyframes.

This is the DISPLAY tier (PLAN: tip-and-cue for compute). Full-resolution data
stays on S3 for scoring/training; the browser only ever sees these keyframes.

Usage:
  python scripts/ingest/build_ais_tracks.py 2024-11-18 [--out frontend/public/data/ais]

Output: <out>/tracks_<date>.json  — { meta, vessels:[{mmsi,name,type,kf,gaps}] }
  kf  = [[t_epoch_s, lon, lat, sog, cog], ...]  (keyframes)
  gaps = [[t0, t1], ...]  AIS-dark intervals (not interpolated across visually)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import duckdb
import numpy as np

ROOT = Path(__file__).resolve().parents[2]

BBOX = (9.0, 52.0, 30.0, 66.0)  # Baltic: min_lon, min_lat, max_lon, max_lat
THIN_SECONDS = 30
DP_TOLERANCE_DEG = 0.0015  # ~150 m
GAP_SECONDS = 600  # >10 min between pings = AIS gap

# Danish AIS "Ship type" string -> normalized ShipType enum (see shared encoding)
SHIP_TYPE_MAP = {
    "tanker": "tanker", "cargo": "cargo", "fishing": "fishing",
    "passenger": "passenger", "hsc": "high_speed", "wig": "wing_in_ground",
    "tug": "tug", "pilot": "pilot", "dredging": "dredger",
    "military": "military", "law enforcement": "law_enforcement",
    "search and rescue": "search_and_rescue", "sar": "search_and_rescue",
    "pleasure": "pleasure", "sailing": "pleasure", "port tender": "port_tender",
    "anti-pollution": "anti_pollution", "medical": "other", "diving": "other",
}


def norm_type(raw: str | None) -> str:
    if not raw:
        return "unknown"
    s = str(raw).strip().lower()
    for key, val in SHIP_TYPE_MAP.items():
        if key in s:
            return val
    return "other"


def dp_keep(x: np.ndarray, y: np.ndarray, tol: float) -> np.ndarray:
    """Douglas-Peucker — return a boolean mask of points to keep (iterative)."""
    n = len(x)
    keep = np.zeros(n, dtype=bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        xi, yi, xj, yj = x[i], y[i], x[j], y[j]
        dx, dy = xj - xi, yj - yi
        seg2 = dx * dx + dy * dy
        if seg2 == 0:
            d = np.hypot(x[i + 1 : j] - xi, y[i + 1 : j] - yi)
        else:
            t = ((x[i + 1 : j] - xi) * dx + (y[i + 1 : j] - yi) * dy) / seg2
            px, py = xi + t * dx, yi + t * dy
            d = np.hypot(x[i + 1 : j] - px, y[i + 1 : j] - py)
        k = int(np.argmax(d))
        if d[k] > tol:
            idx = i + 1 + k
            keep[idx] = True
            stack.append((i, idx))
            stack.append((idx, j))
    return keep


def build(date_str: str, out_rel: str = "frontend/public/data/ais", quiet: bool = False) -> dict:
    """Build one day's track tile. Returns stats dict. Idempotent caller skips existing."""
    y, m, d = (int(p) for p in date_str.split("-"))

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET enable_progress_bar=false")
    # Survive a slow/contended home link: generous timeout + retries, keep-alive.
    for stmt in (
        "SET http_timeout=90000",        # 90s/request — fail-fast; the batch's
        "SET http_retries=2",            #   per-day subprocess timeout is the backstop
        "SET http_retry_wait_ms=500",
        "SET http_keep_alive=true",
    ):
        try:
            con.execute(stmt)
        except duckdb.Error:
            pass  # older duckdb may not have all knobs
    # credential_chain works with both long-term creds (local ~/.aws) and an
    # EC2 instance-role's temporary creds (session token) — so the in-region
    # batch needs no key handling.
    con.execute("CREATE SECRET aws (TYPE s3, PROVIDER credential_chain, REGION 'eu-west-3')")
    src = f"s3://edth2026-baltic/ais/parquet/source=danish/year={y}/month={m:02d}/day={d:02d}/*.parquet"
    args_date = date_str
    if not quiet:
        print(f"[ais tracks] {date_str} — reading + thinning to {THIN_SECONDS}s ...", flush=True)
    # Thin to one ping per vessel per 30s bucket (earliest), keep static fields.
    q = f"""
    WITH base AS (
      SELECT MMSI AS mmsi, ts, Longitude AS lon, Latitude AS lat,
             SOG AS sog, COG AS cog, Name AS name, "Ship type" AS stype,
             time_bucket(INTERVAL '{THIN_SECONDS} seconds', ts) AS tb,
             row_number() OVER (PARTITION BY MMSI, time_bucket(INTERVAL '{THIN_SECONDS} seconds', ts) ORDER BY ts) AS rn
      FROM read_parquet('{src}')
      WHERE Longitude BETWEEN {BBOX[0]} AND {BBOX[2]} AND Latitude BETWEEN {BBOX[1]} AND {BBOX[3]}
        AND Longitude IS NOT NULL AND Latitude IS NOT NULL
    )
    SELECT mmsi, epoch(ts)::BIGINT AS t, lon, lat,
           coalesce(sog, 0) AS sog, coalesce(cog, 0) AS cog, name, stype
    FROM base WHERE rn = 1 ORDER BY mmsi, t
    """
    df = con.execute(q).fetch_df()
    if not quiet:
        print(f"  thinned rows: {len(df):,}  vessels: {df['mmsi'].nunique():,}", flush=True)

    vessels = []
    kf_total = 0
    for mmsi, g in df.groupby("mmsi", sort=False):
        if len(g) < 2:
            continue
        t = g["t"].to_numpy()
        lon = g["lon"].to_numpy()
        lat = g["lat"].to_numpy()
        sog = g["sog"].to_numpy()
        cog = g["cog"].to_numpy()
        # simplify in locally-isotropic space (scale lon by cos(lat))
        coslat = np.cos(np.radians(lat.mean()))
        keep = dp_keep(lon * coslat, lat, DP_TOLERANCE_DEG)
        ki = np.where(keep)[0]
        kf = [[int(t[i]), round(float(lon[i]), 5), round(float(lat[i]), 5),
               round(float(sog[i]), 1), int(round(float(cog[i])))] for i in ki]
        # AIS gaps on the thinned series (dark intervals)
        dt = np.diff(t)
        gaps = [[int(t[i]), int(t[i + 1])] for i in np.where(dt > GAP_SECONDS)[0]]
        name = next((str(v) for v in g["name"] if isinstance(v, str) and v.strip()), "")
        stype = next((str(v) for v in g["stype"] if isinstance(v, str) and v.strip()), "")
        vessels.append({
            "mmsi": int(mmsi),
            "name": name.strip().title() or f"MMSI {int(mmsi)}",
            "type": norm_type(stype),
            "kf": kf,
            "gaps": gaps,
        })
        kf_total += len(kf)

    if not vessels:
        return {"date": args_date, "vessels": 0, "keyframes": 0, "mb": 0.0}
    t0 = int(df["t"].min())
    t1 = int(df["t"].max())
    out_dir = ROOT / out_rel
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"tracks_{date_str}.json"
    tile = {
        "meta": {
            "date": date_str, "start": t0, "end": t1, "bbox": list(BBOX),
            "source": "Danish Maritime Authority AIS (downsampled keyframes)",
            "thin_seconds": THIN_SECONDS, "dp_tolerance_deg": DP_TOLERANCE_DEG,
            "vessels": len(vessels), "keyframes": kf_total,
        },
        "vessels": vessels,
    }
    out.write_text(json.dumps(tile, separators=(",", ":")), encoding="utf-8")
    mb = out.stat().st_size / 1_048_576
    if not quiet:
        print(f"  -> {out.relative_to(ROOT)}  {mb:.1f} MB · {len(vessels):,} vessels · {kf_total:,} keyframes "
              f"({kf_total / max(len(df),1) * 100:.1f}% of thinned)", flush=True)
    return {"date": args_date, "vessels": len(vessels), "keyframes": kf_total, "mb": round(mb, 2)}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("date", help="YYYY-MM-DD")
    ap.add_argument("--out", default="frontend/public/data/ais")
    args = ap.parse_args(argv)
    build(args.date, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
