"""Search Element84's free STAC catalog for Sentinel-1/-2 scenes around each Baltic incident.

Outputs:
  data/reference/sentinel_scenes.csv -- one row per matched scene with download metadata
  data/reference/sentinel_scenes_README.md -- summary

No auth required for searching. Actual scene download requires either:
  - AWS requester-pays for Sentinel-2 L2A: s3://sentinel-cogs/ (free for GET, you pay egress)
  - Copernicus account for original ESA archive
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

STAC_ENDPOINT = "https://earth-search.aws.element84.com/v1/search"

INCIDENTS = [
    # (incident_id, name, lat, lon, date_utc)
    ("INC-2022-09-26", "Nord Stream", 55.50, 15.40, "2022-09-26"),
    ("INC-2023-10-08", "Balticconnector / Newnew Polar Bear", 59.90, 23.40, "2023-10-08"),
    ("INC-2024-11-17", "BCS East-West / Yi Peng 3", 55.30, 17.50, "2024-11-17"),
    ("INC-2024-11-18", "C-Lion1 / Yi Peng 3", 55.00, 16.00, "2024-11-18"),
    ("INC-2024-12-25", "Estlink 2 / Eagle S", 60.30, 26.50, "2024-12-25"),
    ("INC-2025-01-26", "Latvia-Sweden Gotland / Vezhen", 57.60, 19.50, "2025-01-26"),
    ("INC-2025-02-21", "Germany-Finland Cinia cable", 57.50, 19.50, "2025-02-21"),
    ("INC-2025-12-31", "Finland-Estonia Elisa / Fitburg", 60.00, 25.00, "2025-12-31"),
    ("INC-2026-01-02", "Lithuania-Latvia Sventoji-Liepaja", 56.10, 20.70, "2026-01-02"),
]

BBOX_DEG_HALFWIDTH = 1.0  # ±1° of lat/lon around the event point ≈ 110 km
WINDOW_DAYS = 7  # ± this many days


def search(collection: str, bbox: list[float], dt_range: str, limit: int = 30) -> list[dict]:
    body = {
        "collections": [collection],
        "bbox": bbox,
        "datetime": dt_range,
        "limit": limit,
    }
    r = requests.post(STAC_ENDPOINT, json=body, timeout=60,
                       headers={"User-Agent": "edth2026-baltic-prep/0.1"})
    r.raise_for_status()
    return r.json().get("features", [])


def main() -> int:
    out_csv = Path("data/reference/sentinel_scenes.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "incident_id", "incident_name", "incident_date", "collection",
        "scene_id", "scene_datetime", "cloud_cover", "platform",
        "bbox_minlon", "bbox_minlat", "bbox_maxlon", "bbox_maxlat",
        "self_href",
    ]
    rows: list[dict] = []
    summary: list[str] = []

    for inc_id, name, lat, lon, date_str in INCIDENTS:
        d = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        start = (d - timedelta(days=WINDOW_DAYS)).isoformat()
        end = (d + timedelta(days=WINDOW_DAYS)).isoformat()
        dt_range = f"{start}/{end}"
        bbox = [lon - BBOX_DEG_HALFWIDTH, lat - BBOX_DEG_HALFWIDTH,
                lon + BBOX_DEG_HALFWIDTH, lat + BBOX_DEG_HALFWIDTH]

        s2_hits = search("sentinel-2-l2a", bbox, dt_range)
        s1_hits = search("sentinel-1-grd", bbox, dt_range)
        summary.append(f"{inc_id}  {name[:40]:40s}  S2={len(s2_hits):3d}  S1={len(s1_hits):3d}")
        print(summary[-1], flush=True)

        for feat in s2_hits:
            p = feat.get("properties", {})
            fbb = feat.get("bbox", [None]*4)
            self_href = next((l["href"] for l in feat.get("links", [])
                              if l.get("rel") == "self"), "")
            rows.append({
                "incident_id": inc_id,
                "incident_name": name,
                "incident_date": date_str,
                "collection": "sentinel-2-l2a",
                "scene_id": feat["id"],
                "scene_datetime": p.get("datetime", ""),
                "cloud_cover": p.get("eo:cloud_cover", ""),
                "platform": p.get("platform", ""),
                "bbox_minlon": fbb[0], "bbox_minlat": fbb[1],
                "bbox_maxlon": fbb[2], "bbox_maxlat": fbb[3],
                "self_href": self_href,
            })
        for feat in s1_hits:
            p = feat.get("properties", {})
            fbb = feat.get("bbox", [None]*4)
            self_href = next((l["href"] for l in feat.get("links", [])
                              if l.get("rel") == "self"), "")
            rows.append({
                "incident_id": inc_id,
                "incident_name": name,
                "incident_date": date_str,
                "collection": "sentinel-1-grd",
                "scene_id": feat["id"],
                "scene_datetime": p.get("datetime", ""),
                "cloud_cover": "",
                "platform": p.get("platform", ""),
                "bbox_minlon": fbb[0], "bbox_minlat": fbb[1],
                "bbox_maxlon": fbb[2], "bbox_maxlat": fbb[3],
                "self_href": self_href,
            })

    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\nWrote {len(rows)} rows -> {out_csv}")
    print(f"\nSummary:")
    for s in summary:
        print(f"  {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
