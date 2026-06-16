"""Batch-build replay track tiles for the whole AIS archive.

Lists the day partitions present in the LOCAL parquet archive, then builds a
keyframe tile per day (skipping any already built), in parallel. Each day runs
in its OWN fresh subprocess with a hard timeout — so memory can't creep across
days (no OOM) and one pathological read can't stall the batch (the day is killed
+ skipped). Idempotent and resumable.

S3 retired — day enumeration walks the local filesystem
(data/ais/parquet/source=danish/year=*/month=*/day=*); no AWS needed.

  python scripts/ingest/build_all_tracks.py                 # all available days
  python scripts/ingest/build_all_tracks.py 2024-11 2024-12 # only these months
  python scripts/ingest/build_all_tracks.py --workers 20
"""
from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "frontend/public/data/ais"
DAY_SCRIPT = HERE / "build_ais_tracks.py"
PREFIX = "ais/parquet/source=danish"
BUCKET = "edth2026-baltic"
# Local parquet root the per-day builder also reads from (S3 retired).
PARQUET_ROOT = ROOT / "data" / "ais" / "parquet" / "source=danish"
PER_DAY_TIMEOUT = 150  # seconds — kill + skip a day that hangs


def local_days(month_filter: list[str]) -> list[str]:
    """Enumerate day partitions from the LOCAL parquet archive (S3 retired).

    Walks data/ais/parquet/source=danish/year=*/month=*/day=* on disk instead of
    `aws s3 ls`, so the batch runs with no AWS credentials.
    """
    days: list[str] = []
    for day_dir in PARQUET_ROOT.glob("year=*/month=*/day=*"):
        if not day_dir.is_dir():
            continue
        try:
            y = day_dir.parent.parent.name.split("year=")[1]
            m = day_dir.parent.name.split("month=")[1]
            d = day_dir.name.split("day=")[1]
        except IndexError:
            continue
        if month_filter and f"{y}-{m}" not in month_filter:
            continue
        days.append(f"{y}-{m}-{d}")
    return sorted(days)


def build_one(date_str: str) -> tuple[str, str]:
    """Run the per-day builder in a fresh subprocess. Returns (date, status)."""
    try:
        r = subprocess.run(
            [sys.executable, str(DAY_SCRIPT), date_str],
            capture_output=True, text=True, timeout=PER_DAY_TIMEOUT,
        )
        if (OUT / f"tracks_{date_str}.json").exists():
            return date_str, "ok"
        if r.returncode != 0:
            return date_str, f"err:{(r.stderr or '').strip().splitlines()[-1][:80] if r.stderr.strip() else 'rc'+str(r.returncode)}"
        return date_str, "empty"  # ran fine but no vessels that day
    except subprocess.TimeoutExpired:
        return date_str, "timeout"


def main(argv: list[str]) -> int:
    workers = 16
    months = []
    i = 0
    while i < len(argv):
        if argv[i] == "--workers":
            workers = int(argv[i + 1]); i += 2
        else:
            months.append(argv[i]); i += 1

    OUT.mkdir(parents=True, exist_ok=True)
    days = local_days(months)
    todo = [d for d in days if not (OUT / f"tracks_{d}.json").exists()]
    print(f"[batch] {len(days)} days local · {len(days) - len(todo)} built · {len(todo)} to do · {workers} workers", flush=True)

    done = ok = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(build_one, d) for d in todo]
        for f in as_completed(futs):
            date_str, status = f.result()
            done += 1
            if status == "ok":
                ok += 1
            else:
                print(f"  [{done}/{len(todo)}] {date_str} {status}", flush=True)
            if done % 50 == 0 or done == len(todo):
                print(f"  [{done}/{len(todo)}] built ok={ok}", flush=True)
    print(f"[batch] complete — {ok}/{len(todo)} tiles built", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
