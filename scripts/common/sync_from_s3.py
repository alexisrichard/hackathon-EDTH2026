"""Sync large data layers from s3://edth2026-baltic/ to local data/.

Used by teammates after cloning the repo to pull files that are too large for git
(EMODnet cables combined, Marine Regions EEZ, AIS Parquet snapshots).

Usage:
  python scripts/common/sync_from_s3.py geo            # all geo/ layers
  python scripts/common/sync_from_s3.py reference      # sanctions + incidents
  python scripts/common/sync_from_s3.py ais YYYY-MM-DD # one day of Danish AIS
  python scripts/common/sync_from_s3.py all            # everything (~hundreds of MB)
"""
from __future__ import annotations

import subprocess
import sys

BUCKET = "edth2026-baltic"

SYNCS: dict[str, tuple[str, str]] = {
    "geo": (f"s3://{BUCKET}/geo/", "data/geo/"),
    "reference": (f"s3://{BUCKET}/reference/", "data/reference/"),
}


def run(args: list[str]) -> int:
    print(f"$ {' '.join(args)}", flush=True)
    return subprocess.call(args)


def cmd_sync_prefix(label: str) -> int:
    src, dst = SYNCS[label]
    return run(["aws", "s3", "sync", src, dst, "--exclude", "*.keep"])


def cmd_ais_day(date_str: str) -> int:
    # YYYY-MM-DD
    y, m, d = date_str.split("-")
    src = f"s3://{BUCKET}/ais/parquet/source=danish/year={y}/month={m}/day={d}/"
    dst = f"data/ais/parquet/source=danish/year={y}/month={m}/day={d}/"
    return run(["aws", "s3", "sync", src, dst])


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    cmd = argv[1]
    if cmd in SYNCS:
        return cmd_sync_prefix(cmd)
    if cmd == "ais" and len(argv) >= 3:
        return cmd_ais_day(argv[2])
    if cmd == "all":
        rc = 0
        for label in SYNCS:
            rc |= cmd_sync_prefix(label)
        return rc
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
