"""Extract one vessel's per-day track history from the AIS keyframe tiles.

The replay tiles (`tracks_<date>.json`, built locally by `build_ais_tracks.py`;
S3 retired) are partitioned by day.
The scoring engine, by contrast, needs a *per-vessel* view: every day-record
for one MMSI, so `scoring.behavioral.behavioral_history` can compute that
vessel's prior. This script pivots day-partitioned tiles into that view.

Pass `--before <date>` to honor the no-look-ahead rule when building a prior:
only day-records strictly before that date are collected.

Usage:
  python scripts/ingest/vessel_history.py 414270000 --before 2024-11-18
  python scripts/ingest/vessel_history.py 414270000 --out data/ais/by_vessel

Output: <out>/<mmsi>.json — { mmsi, name, days:[{date, kf, gaps}, ...] }
matching the input `scoring.behavioral.behavioral_history` expects.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TILES_DIR = ROOT / "data" / "ais" / "tiles"
DEFAULT_OUT_DIR = ROOT / "data" / "ais" / "by_vessel"


def _tile_date(path: Path) -> str:
    # tracks_2024-11-18.json -> 2024-11-18
    return path.stem.replace("tracks_", "")


def iter_tiles(
    tiles_dir: Path, before: str | None = None, after: str | None = None
):
    """Yield (date, path) for tiles within [after, before), sorted by date.

    ISO dates sort lexicographically, so string comparison is correct and lets
    us skip out-of-range files without opening them.
    """
    for path in sorted(tiles_dir.glob("tracks_*.json")):
        day = _tile_date(path)
        if before is not None and day >= before:
            continue
        if after is not None and day < after:
            continue
        yield day, path


def extract_vessel_history(
    mmsi: int,
    tiles_dir: Path = DEFAULT_TILES_DIR,
    before: str | None = None,
    after: str | None = None,
) -> dict:
    """Collect every day-record for ``mmsi`` from the tiles in range."""
    days: list[dict] = []
    name: str | None = None
    for day, path in iter_tiles(tiles_dir, before=before, after=after):
        tile = json.loads(path.read_text(encoding="utf-8"))
        for vessel in tile.get("vessels", []):
            if vessel.get("mmsi") == mmsi:
                name = name or vessel.get("name")
                days.append(
                    {"date": day, "kf": vessel.get("kf", []), "gaps": vessel.get("gaps", [])}
                )
                break
    return {"mmsi": mmsi, "name": name, "days": days}


def _summary(history: dict) -> str:
    days = history["days"]
    total_kf = sum(len(d["kf"]) for d in days)
    total_gaps = sum(len(d["gaps"]) for d in days)
    span = f"{days[0]['date']} → {days[-1]['date']}" if days else "(none)"
    return (
        f"mmsi={history['mmsi']} name={history['name']!r}\n"
        f"  days={len(days)}  span={span}  keyframes={total_kf}  gaps={total_gaps}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mmsi", type=int, help="vessel MMSI to extract")
    parser.add_argument("--before", help="only days strictly before this date (YYYY-MM-DD)")
    parser.add_argument("--after", help="only days on/after this date (YYYY-MM-DD)")
    parser.add_argument("--tiles-dir", type=Path, default=DEFAULT_TILES_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)

    if not args.tiles_dir.exists():
        parser.error(f"tiles dir not found: {args.tiles_dir}")

    history = extract_vessel_history(
        args.mmsi, tiles_dir=args.tiles_dir, before=args.before, after=args.after
    )
    args.out.mkdir(parents=True, exist_ok=True)
    out_path = args.out / f"{args.mmsi}.json"
    out_path.write_text(json.dumps(history), encoding="utf-8")
    print(_summary(history))
    print(f"  wrote {out_path}")
    return 0 if history["days"] else 1


if __name__ == "__main__":
    sys.exit(main())
