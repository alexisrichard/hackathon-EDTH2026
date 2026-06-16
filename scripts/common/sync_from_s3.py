"""RETIRED — the project's S3 bucket (s3://edth2026-baltic/) has been deleted.

This script used to pull the large data layers from S3. The bucket no longer exists
(retired to stop incurring storage cost). Nothing here downloads anymore; instead it
prints the public-source rebuild command for whatever layer you ask for, so an old
muscle-memory invocation guides you to the new path instead of failing cryptically.

Everything regenerates from its ORIGINAL public source — see DATA_GUIDE.md. The demo
itself needs none of this: the frontend + scoring engine run from data committed in
git (cues, geo/incident overlays, and the hero-incident AIS replay days).
"""
from __future__ import annotations

import sys

# label -> (what it was, how to rebuild it from the public source now)
REBUILD: dict[str, tuple[str, str]] = {
    "geo": (
        "criticality / infrastructure GeoJSON layers (OSM, EMODnet, HELCOM, NE, GMRT — all public)",
        "python scripts/geo/fetch_osm_layers.py  (+ fetch_emodnet_layers.py, fetch_helcom.py, "
        "fetch_marine_regions_eez.py, fetch_natural_earth.py, fetch_bathymetry.py) — see DATA_GUIDE.md",
    ),
    "reference": (
        "sanctions, incidents, marine weather, registry lookups",
        "python scripts/reference/fetch_sanctions.py  &&  python scripts/ingest/fetch_marine_weather.py",
    ),
    "kaggle": (
        "10 Kaggle ML datasets (~24 GB) — needs a free Kaggle account (~/.kaggle/kaggle.json)",
        "python scripts/ingest/fetch_kaggle.py --skip-s3",
    ),
    "ais": (
        "Danish AIS parquet (Danish Maritime Authority, public)",
        "python scripts/ingest/danish_ais.py date YYYY-MM-DD   # or `… incidents` for the incident windows",
    ),
}


def main(argv: list[str]) -> int:
    print(__doc__)
    asked = argv[1] if len(argv) > 1 else None
    print("Rebuild from public sources:\n")
    for label, (what, how) in REBUILD.items():
        marker = "→" if label == asked else " "
        print(f" {marker} {label:10s} {what}\n              {how}\n")
    if asked and asked not in REBUILD and asked != "all":
        print(f"(unknown layer '{asked}' — pick one of: {', '.join(REBUILD)})")
    # Non-zero so any script that chained on a successful sync notices the change.
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
