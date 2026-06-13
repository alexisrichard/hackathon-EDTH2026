"""Batch-build replay track tiles for the whole AIS archive.

Lists the day partitions present on S3, then builds a keyframe tile per day
(skipping any already built), in parallel. Idempotent and resumable — safe to
re-run; it only fills gaps.

  python scripts/ingest/build_all_tracks.py                # all available days
  python scripts/ingest/build_all_tracks.py 2024-11 2024-12  # only these months
  python scripts/ingest/build_all_tracks.py --workers 8

Tiles land in frontend/public/data/ais/tracks_<date>.json (gitignored in bulk;
host the set on S3/CDN for the deployed app — see frontend/README).
"""
from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_ais_tracks import build  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "frontend/public/data/ais"
PREFIX = "ais/parquet/source=danish"
BUCKET = "edth2026-baltic"


def s3_days(month_filter: list[str]) -> list[str]:
    """List YYYY-MM-DD day partitions present on S3 (optionally filtered by YYYY-MM)."""
    days: list[str] = []
    years = subprocess.run(
        ["aws", "s3", "ls", f"s3://{BUCKET}/{PREFIX}/"], capture_output=True, text=True
    ).stdout
    for yline in years.splitlines():
        if "year=" not in yline:
            continue
        y = yline.split("year=")[1].strip().rstrip("/")
        months = subprocess.run(
            ["aws", "s3", "ls", f"s3://{BUCKET}/{PREFIX}/year={y}/"], capture_output=True, text=True
        ).stdout
        for mline in months.splitlines():
            if "month=" not in mline:
                continue
            m = mline.split("month=")[1].strip().rstrip("/")
            if month_filter and f"{y}-{m}" not in month_filter:
                continue
            dd = subprocess.run(
                ["aws", "s3", "ls", f"s3://{BUCKET}/{PREFIX}/year={y}/month={m}/"],
                capture_output=True, text=True,
            ).stdout
            for dline in dd.splitlines():
                if "day=" in dline:
                    d = dline.split("day=")[1].strip().rstrip("/")
                    days.append(f"{y}-{m}-{d}")
    return sorted(days)


def _build_one(date_str: str) -> dict:
    try:
        return build(date_str, quiet=True)
    except Exception as e:  # one bad day shouldn't kill the batch
        return {"date": date_str, "error": str(e)[:120]}


def main(argv: list[str]) -> int:
    workers = 6
    months = []
    i = 0
    while i < len(argv):
        if argv[i] == "--workers":
            workers = int(argv[i + 1])
            i += 2
        else:
            months.append(argv[i])
            i += 1

    OUT.mkdir(parents=True, exist_ok=True)
    days = s3_days(months)
    todo = [d for d in days if not (OUT / f"tracks_{d}.json").exists()]
    print(f"[batch] {len(days)} days on S3 · {len(days) - len(todo)} already built · {len(todo)} to do · {workers} workers", flush=True)

    done = 0
    kf = 0
    # max_tasks_per_child recycles workers so per-day pandas memory can't creep
    # and OOM-kill a worker (which would poison the whole pool).
    with ProcessPoolExecutor(max_workers=workers, max_tasks_per_child=8) as ex:
        futs = {ex.submit(_build_one, d): d for d in todo}
        for f in as_completed(futs):
            try:
                r = f.result()
            except Exception as e:  # a dead worker shouldn't abort the batch
                print(f"  [{done}/{len(todo)}] {futs[f]} POOL-ERROR {str(e)[:80]}", flush=True)
                done += 1
                continue
            done += 1
            if "error" in r:
                print(f"  [{done}/{len(todo)}] {r['date']} ERROR {r['error']}", flush=True)
            else:
                kf += r["keyframes"]
                if done % 20 == 0 or done == len(todo):
                    print(f"  [{done}/{len(todo)}] {r['date']} · {r['vessels']} vessels · running kf={kf:,}", flush=True)
    print(f"[batch] complete — {done} tiles built, {kf:,} keyframes total", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
