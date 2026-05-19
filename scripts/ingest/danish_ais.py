"""Ingest Danish Maritime Authority AIS data.

Data source: anonymous S3 bucket `aisdata.ais.dk` (eu-central-1)
  - Years 2006-2024 Feb: monthly zips `<year>/aisdk-<year>-<mm>.zip` (~15 GB each)
  - 2024 Mar - 2025: daily zips `<year>/aisdk-<year>-<mm>-<dd>.zip` (~500 MB each)
  - 2025 most recent + 2026: daily zips at root `aisdk-<year>-<mm>-<dd>.zip`

CSV schema (26 columns, comma-separated, decimal comma):
  Timestamp ("31/12/2015 23:59:59"), Type of mobile, MMSI, Latitude, Longitude,
  Navigational status, ROT, SOG, COG, Heading, IMO, Callsign, Name, Ship type,
  Cargo type, Width, Length, Type of position fixing device, Draught,
  Destination, ETA, Data source type, Size A, Size B, Size C, Size D

Pipeline per file:
  1. Download .zip from aisdata.ais.dk (anonymous S3)
  2. Stream-extract inner CSV via zipfile.open() (no full disk extraction)
  3. Read in chunks with pandas, filter to Baltic bbox (lat 52-66, lon 9-30)
  4. Group by date, write per-day Parquet via pyarrow (zstd compression)
  5. Upload Parquet partition to s3://edth2026-baltic/ais/parquet/...
  6. Delete local zip + temp Parquet files

Output layout:
  s3://edth2026-baltic/ais/parquet/source=danish/year=YYYY/month=MM/day=DD/part-0000.parquet

Usage:
  python scripts/ingest/danish_ais.py incidents          # all 9 incident windows
  python scripts/ingest/danish_ais.py date 2024-12-25    # one specific day
  python scripts/ingest/danish_ais.py month 2024-11      # one month (may be a monthly zip)
  python scripts/ingest/danish_ais.py range 2024-11-14 2024-11-21
"""

from __future__ import annotations

import io
import re
import shutil
import sys
import time
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

import urllib.request

import boto3
import requests
from botocore import UNSIGNED
from botocore.client import Config

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# ----- Config -----

SOURCE_BUCKET = "aisdata.ais.dk"
SOURCE_REGION = "eu-central-1"

DEST_BUCKET = "edth2026-baltic"
DEST_REGION = "eu-west-3"
DEST_PREFIX = "ais/parquet/source=danish"

CACHE_DIR = Path("data/ais/cache")
PARQUET_DIR = Path("data/ais/parquet")
CACHE_DIR.mkdir(parents=True, exist_ok=True)
PARQUET_DIR.mkdir(parents=True, exist_ok=True)

BBOX = (52.0, 66.0, 9.0, 30.0)  # min_lat, max_lat, min_lon, max_lon

# Filtering done in pandas; reading is chunked so we stay under ~2 GB RAM
READ_CHUNK_ROWS = 1_000_000

# Bandwidth throttle for the download phase. 0 = unlimited; else target Mbps.
# 25 Mbps ≈ 3.1 MB/s — leaves headroom on a 100 Mbps link for everyday use.
DOWNLOAD_MBPS = 25

INCIDENT_WINDOWS: list[tuple[date, date]] = [
    # (start_inclusive, end_inclusive) for each incident ±3 days
    (date(2022, 9, 1),  date(2022, 9, 30)),    # Nord Stream — monthly file covers it
    (date(2023, 10, 1), date(2023, 10, 31)),   # Balticconnector — monthly file covers it
    (date(2024, 11, 14), date(2024, 11, 21)),  # Yi Peng 3
    (date(2024, 12, 22), date(2024, 12, 28)),  # Eagle S
    (date(2025, 1, 23),  date(2025, 1, 29)),   # Vezhen
    (date(2025, 2, 18),  date(2025, 2, 24)),   # Cinia Germany-Finland
    (date(2025, 12, 28), date(2026, 1, 4)),    # Fitburg + Sventoji-Liepaja overlap
]

# Anonymous client for source bucket
_anon = boto3.client("s3", region_name=SOURCE_REGION, config=Config(signature_version=UNSIGNED))
# Authenticated client for our destination bucket
_dest = boto3.client("s3", region_name=DEST_REGION)


def s3_key_for_date(d: date) -> tuple[str, str]:
    """Return (s3_key, file_type) where file_type in {'daily', 'monthly'}."""
    # Daily under year prefix: 2024 Mar onwards through 2025
    # Daily at root: 2025 mid-Mar onwards (rough boundary — try both)
    # Monthly under year prefix: 2006 - 2024 Feb
    d_str = d.strftime("%Y-%m-%d")
    if d >= date(2024, 3, 1):
        # Try year-prefixed first, fall back to root
        prefixed = f"{d.year}/aisdk-{d_str}.zip"
        root = f"aisdk-{d_str}.zip"
        # Probe (cheap HEAD); choose whichever exists
        for key in (prefixed, root):
            try:
                _anon.head_object(Bucket=SOURCE_BUCKET, Key=key)
                return key, "daily"
            except _anon.exceptions.ClientError:
                continue
        raise FileNotFoundError(f"No daily file for {d_str}")
    else:
        return f"{d.year}/aisdk-{d.year}-{d.month:02d}.zip", "monthly"


def download(key: str) -> Path:
    """Download zip from source bucket to local cache. Returns local path."""
    name = Path(key).name
    local = CACHE_DIR / name
    if local.exists() and local.stat().st_size > 0:
        print(f"  cache hit: {local.name} ({local.stat().st_size // 1024 // 1024} MB)", flush=True)
        return local
    # Anonymous S3 bucket → public HTTPS. Plain streaming GET avoids the
    # boto3/aws-cli multipart-then-atomic-rename pattern that races with
    # Windows AV/indexer (WinError 32). Path-style URL because the bucket
    # name 'aisdata.ais.dk' has dots that break the *.s3.region cert.
    url = f"https://s3.{SOURCE_REGION}.amazonaws.com/{SOURCE_BUCKET}/{key}"
    print(f"  downloading {url} -> {local}  (throttle: {DOWNLOAD_MBPS} Mbps)", flush=True)
    t0 = time.time()
    bytes_done = 0
    last_log = t0
    # Token-bucket throttle: aim for DOWNLOAD_MBPS, smoothed across small chunks.
    chunk_size = 256 * 1024  # 256 KB — gives smooth pacing without per-byte overhead
    target_bps = (DOWNLOAD_MBPS * 1_000_000 / 8) if DOWNLOAD_MBPS > 0 else 0
    with requests.get(url, stream=True, timeout=(30, 600)) as r:
        r.raise_for_status()
        with open(local, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if not chunk:
                    continue
                f.write(chunk)
                bytes_done += len(chunk)
                # Pace against the target: if we're ahead of schedule, sleep.
                if target_bps > 0:
                    elapsed = time.time() - t0
                    expected = bytes_done / target_bps
                    if expected > elapsed:
                        time.sleep(expected - elapsed)
                now = time.time()
                if now - last_log > 30:
                    mb = bytes_done / 1_048_576
                    elapsed = now - t0
                    rate = mb / max(elapsed, 1)
                    print(f"    ...{mb:>6.0f} MB  ({rate:.1f} MB/s)", flush=True)
                    last_log = now
    mb = local.stat().st_size / 1_048_576
    dt = time.time() - t0
    print(f"    downloaded {mb:.0f} MB in {dt:.0f}s ({mb/max(dt,1):.0f} MB/s)", flush=True)
    return local


# Column types and Danish CSV quirks
COLUMNS = [
    "Timestamp", "Type of mobile", "MMSI", "Latitude", "Longitude",
    "Navigational status", "ROT", "SOG", "COG", "Heading",
    "IMO", "Callsign", "Name", "Ship type", "Cargo type",
    "Width", "Length", "Type of position fixing device", "Draught",
    "Destination", "ETA", "Data source type",
    "Size A", "Size B", "Size C", "Size D",
]

DTYPE_MAP = {c: "string" for c in COLUMNS}  # read all as strings, coerce on write


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Strip leading '#' and whitespace from column names (Danish AIS prepends '# ' to first col)."""
    df.columns = [c.lstrip("# ").strip() for c in df.columns]
    return df


def filter_chunk(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce numerics, parse timestamp, filter to Baltic bbox.

    Danish AIS CSVs use '.' decimal (despite the README example showing ',').
    Header has '# ' prefix on first column. Size cols are named A,B,C,D not 'Size A' etc.
    """
    df = _normalize_columns(df)
    for c in ("Latitude", "Longitude", "SOG", "COG", "Heading", "ROT",
              "Width", "Length", "Draught", "A", "B", "C", "D"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    if "MMSI" in df.columns:
        df["MMSI"] = pd.to_numeric(df["MMSI"], errors="coerce").astype("Int64")
    if "IMO" in df.columns:
        df["IMO"] = pd.to_numeric(df["IMO"], errors="coerce").astype("Int64")
    df["ts"] = pd.to_datetime(df["Timestamp"], format="%d/%m/%Y %H:%M:%S", errors="coerce", utc=True)

    mask = (
        df["Latitude"].between(BBOX[0], BBOX[1])
        & df["Longitude"].between(BBOX[2], BBOX[3])
        & df["ts"].notna()
    )
    return df.loc[mask].copy()


def parquet_path(d: date) -> Path:
    p = PARQUET_DIR / f"source=danish" / f"year={d.year}" / f"month={d.month:02d}" / f"day={d.day:02d}"
    p.mkdir(parents=True, exist_ok=True)
    return p / "part-0000.parquet"


def s3_dest_key(d: date) -> str:
    return f"{DEST_PREFIX}/year={d.year}/month={d.month:02d}/day={d.day:02d}/part-0000.parquet"


def process_zip(zip_path: Path, dates_wanted: set[date] | None = None) -> dict[date, Path]:
    """Stream zip → filter → per-day Parquet. Closes + uploads + deletes each day's
    output as soon as its inner CSV finishes — keeps memory + disk bounded even on
    monthly zips with 30 days inside.
    """
    print(f"  processing {zip_path.name}...", flush=True)
    t0 = time.time()
    all_paths: dict[date, Path] = {}
    rows_total = 0
    rows_kept = 0

    with zipfile.ZipFile(zip_path) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            print(f"    NO CSV inside zip!", flush=True)
            return {}
        for csv_idx, csv_name in enumerate(csv_names):
            # Writers scoped to this inner CSV. For monthly zips with one CSV per
            # day, that's a single writer at a time. Closing+uploading+deleting
            # at end of each CSV keeps RAM and disk bounded.
            writers: dict[date, pq.ParquetWriter] = {}
            local_paths: dict[date, Path] = {}
            csv_rows = 0
            csv_kept = 0
            print(f"    inner [{csv_idx+1}/{len(csv_names)}]: {csv_name}", flush=True)
            with zf.open(csv_name) as raw:
                text = io.TextIOWrapper(raw, encoding="latin-1", newline="")
                reader = pd.read_csv(
                    text,
                    sep=",",
                    chunksize=READ_CHUNK_ROWS,
                    dtype=DTYPE_MAP,
                    low_memory=False,
                    engine="c",
                    on_bad_lines="skip",
                )
                for i, chunk in enumerate(reader):
                    rows_total += len(chunk)
                    csv_rows += len(chunk)
                    filtered = filter_chunk(chunk)
                    if filtered.empty:
                        continue
                    filtered["date_utc"] = filtered["ts"].dt.date
                    for d, g in filtered.groupby("date_utc"):
                        if dates_wanted is not None and d not in dates_wanted:
                            continue
                        rows_kept += len(g)
                        csv_kept += len(g)
                        if d not in writers:
                            out = parquet_path(d)
                            local_paths[d] = out
                            all_paths[d] = out
                            table = pa.Table.from_pandas(g.drop(columns=["date_utc"]), preserve_index=False)
                            writers[d] = pq.ParquetWriter(out, table.schema, compression="zstd")
                            writers[d].write_table(table)
                        else:
                            table = pa.Table.from_pandas(g.drop(columns=["date_utc"]), preserve_index=False)
                            writers[d].write_table(table)
                    if i and i % 20 == 0:
                        print(f"    ... chunk {i}: csv_rows={csv_rows:,} csv_kept={csv_kept:,}", flush=True)

            # Close writers + upload + delete local for this inner CSV before
            # moving to the next CSV. Keeps memory + disk bounded.
            for w in writers.values():
                w.close()
            for d, p in sorted(local_paths.items()):
                if p.exists():
                    key = s3_dest_key(d)
                    mb = p.stat().st_size / 1_048_576
                    try:
                        _dest.upload_file(str(p), DEST_BUCKET, key)
                        print(f"      uploaded day={d} {mb:.1f} MB", flush=True)
                    except Exception as ex:
                        print(f"      upload FAILED day={d}: {ex}", flush=True)
                        continue
                    try:
                        p.unlink()
                    except OSError:
                        pass

    dt = time.time() - t0
    print(f"  done in {dt:.0f}s. total_rows={rows_total:,}, kept={rows_kept:,}, days={len(all_paths)}", flush=True)
    return all_paths


def upload_parquet(paths: dict[date, Path]) -> None:
    for d, p in sorted(paths.items()):
        key = s3_dest_key(d)
        mb = p.stat().st_size / 1_048_576
        print(f"  uploading {p.name} ({mb:.1f} MB) -> s3://{DEST_BUCKET}/{key}", flush=True)
        _dest.upload_file(str(p), DEST_BUCKET, key)


def cleanup(zip_path: Path, paths: dict[date, Path]) -> None:
    if zip_path.exists():
        print(f"  removing local {zip_path.name}", flush=True)
        zip_path.unlink()
    for p in paths.values():
        if p.exists():
            p.unlink()


def process_one_date(d: date, dates_wanted: set[date] | None = None) -> None:
    """Process the source zip containing date d. For daily files dates_wanted is ignored;
    for monthly files, filter to dates_wanted (so we don't write all 30 days when we only need 7).
    Note: process_zip now uploads + deletes per inner CSV; upload_parquet is a no-op safety net.
    """
    try:
        key, kind = s3_key_for_date(d)
    except FileNotFoundError as ex:
        print(f"  SKIP {d}: {ex}", flush=True)
        return
    print(f"\n=== {d} ({kind}) -> s3://{SOURCE_BUCKET}/{key} ===", flush=True)
    local = download(key)
    if kind == "daily":
        paths = process_zip(local, dates_wanted={d})
    else:
        paths = process_zip(local, dates_wanted=dates_wanted)
    upload_parquet(paths)
    cleanup(local, paths)


def s3_dest_exists(d: date) -> bool:
    """Cheap HEAD against our own bucket to see if a day is already done."""
    try:
        _dest.head_object(Bucket=DEST_BUCKET, Key=s3_dest_key(d))
        return True
    except _dest.exceptions.ClientError:
        return False


def process_window(start: date, end: date) -> None:
    """Process dates in [start, end] inclusive. Skips days already in dest S3."""
    dates_in_window = set()
    d = start
    while d <= end:
        dates_in_window.add(d)
        d += timedelta(days=1)

    # Skip dates already in dest
    already_done = {d for d in dates_in_window if s3_dest_exists(d)}
    if already_done:
        print(f"\n  skipping {len(already_done)} dates already in s3://{DEST_BUCKET}", flush=True)
    dates_in_window -= already_done
    if not dates_in_window:
        print("  nothing to do", flush=True)
        return

    # Group by source zip (one monthly zip can serve up to 31 dates)
    seen_keys: set[str] = set()
    for d in sorted(dates_in_window):
        try:
            key, kind = s3_key_for_date(d)
        except FileNotFoundError as ex:
            print(f"  SKIP {d}: {ex}", flush=True)
            continue
        if key in seen_keys:
            continue
        seen_keys.add(key)
        print(f"\n=== window day {d} -> s3://{SOURCE_BUCKET}/{key} ({kind}) ===", flush=True)
        local = download(key)
        wanted = dates_in_window if kind == "monthly" else {d}
        paths = process_zip(local, dates_wanted=wanted)
        upload_parquet(paths)
        cleanup(local, paths)


def cmd_incidents() -> int:
    print(f"Processing {len(INCIDENT_WINDOWS)} incident windows", flush=True)
    for start, end in INCIDENT_WINDOWS:
        process_window(start, end)
    return 0


def cmd_date(s: str) -> int:
    d = datetime.fromisoformat(s).date()
    process_window(d, d)
    return 0


def cmd_range(start_s: str, end_s: str) -> int:
    start = datetime.fromisoformat(start_s).date()
    end = datetime.fromisoformat(end_s).date()
    process_window(start, end)
    return 0


def cmd_month(s: str) -> int:
    y, m = map(int, s.split("-"))
    start = date(y, m, 1)
    # last day of month
    if m == 12:
        end = date(y, 12, 31)
    else:
        end = date(y, m + 1, 1) - timedelta(days=1)
    process_window(start, end)
    return 0


def cmd_full(end_str: str | None = None) -> int:
    """Full 2022-01-01 → today (or end_str if given). Skips already-done days."""
    from datetime import date as _date
    start = _date(2022, 1, 1)
    end = datetime.fromisoformat(end_str).date() if end_str else _date.today()
    print(f"Full backfill: {start} -> {end} ({(end-start).days} days, will skip already-done)", flush=True)
    process_window(start, end)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd == "incidents":
        return cmd_incidents()
    if cmd == "date" and len(argv) >= 3:
        return cmd_date(argv[2])
    if cmd == "range" and len(argv) >= 4:
        return cmd_range(argv[2], argv[3])
    if cmd == "month" and len(argv) >= 3:
        return cmd_month(argv[2])
    if cmd == "full":
        return cmd_full(argv[2] if len(argv) >= 3 else None)
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
