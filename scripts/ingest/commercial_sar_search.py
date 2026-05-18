"""Walk Umbra & Capella open-data STAC catalogs to find Baltic-area SAR scenes
for each incident window. Outputs metadata only; actual scene download is per-scene.

Umbra: AWS Open Data, CC-BY 4.0
  https://umbra-open-data-catalog.s3.amazonaws.com/stac/
  Layout: <year>/<month>/<scene-id>/<scene>.json

Capella: AWS Open Data, CC-BY-NC 4.0 (non-commercial!)
  https://capella-open-data.s3.amazonaws.com/stac/
  Layout: capella-open-data-by-datetime/<year>/<month>/...

Outputs:
  data/reference/umbra_scenes.csv
  data/reference/capella_scenes.csv
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

UMBRA_BASE = "https://umbra-open-data-catalog.s3.amazonaws.com/stac"
CAPELLA_BASE = "https://capella-open-data.s3.amazonaws.com/stac"

BBOX = (9.0, 52.0, 30.0, 66.0)  # min_lon, min_lat, max_lon, max_lat (Baltic)

INCIDENTS = [
    ("INC-2022-09-26", "Nord Stream", 55.50, 15.40, "2022-09-26"),
    ("INC-2023-10-08", "Balticconnector", 59.90, 23.40, "2023-10-08"),
    ("INC-2024-11-17", "BCS East-West (Yi Peng 3)", 55.30, 17.50, "2024-11-17"),
    ("INC-2024-11-18", "C-Lion1 (Yi Peng 3)", 55.00, 16.00, "2024-11-18"),
    ("INC-2024-12-25", "Estlink 2 (Eagle S)", 60.30, 26.50, "2024-12-25"),
    ("INC-2025-01-26", "Latvia-Sweden Gotland (Vezhen)", 57.60, 19.50, "2025-01-26"),
    ("INC-2025-02-21", "Germany-Finland Cinia", 57.50, 19.50, "2025-02-21"),
    ("INC-2025-12-31", "Finland-Estonia Elisa (Fitburg)", 60.00, 25.00, "2025-12-31"),
    ("INC-2026-01-02", "Lithuania-Latvia Sventoji", 56.10, 20.70, "2026-01-02"),
]

WINDOW_DAYS = 14  # generous window — SAR archives are sparse


def bbox_intersects(a, b):
    """Check if two bboxes [minLon, minLat, maxLon, maxLat] overlap."""
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def fetch_json(url: str, timeout: int = 30):
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "edth2026-baltic-prep/0.1"})
        if r.status_code != 200:
            return None
        return r.json()
    except (requests.exceptions.RequestException, json.JSONDecodeError):
        return None


def walk_umbra(months: set[tuple[int, int]]) -> list[dict]:
    """Walk Umbra STAC catalogs for given (year, month) tuples and return scene metadata."""
    scenes = []
    for year, month in sorted(months):
        url = f"{UMBRA_BASE}/{year}/{year}-{month:02d}/catalog.json"
        cat = fetch_json(url)
        if not cat:
            print(f"  Umbra {year}-{month:02d}: catalog missing", flush=True)
            continue
        # The month catalog has links to individual scene catalogs or items
        item_links = [l for l in cat.get("links", []) if l.get("rel") in ("item", "child")]
        print(f"  Umbra {year}-{month:02d}: {len(item_links)} links", flush=True)
        for il in item_links:
            href = il.get("href", "")
            if href.startswith("./"):
                href = f"{UMBRA_BASE}/{year}/{year}-{month:02d}/" + href[2:]
            elif href.startswith("http"):
                pass
            else:
                href = f"{UMBRA_BASE}/{year}/{year}-{month:02d}/{href}"
            # We could recurse but limit to 60 items per month to bound the walk
            if len(scenes) > 5000:
                break
            item = fetch_json(href)
            if not item:
                continue
            if item.get("type") != "Feature":
                # It's a catalog — descend one level
                for sub in item.get("links", []):
                    if sub.get("rel") == "item":
                        sub_href = sub.get("href", "")
                        if sub_href.startswith("./"):
                            sub_href = href.rsplit("/", 1)[0] + "/" + sub_href[2:]
                        sub_item = fetch_json(sub_href)
                        if sub_item and sub_item.get("type") == "Feature":
                            scenes.append(("umbra", sub_item))
            else:
                scenes.append(("umbra", item))
    return scenes


def walk_capella(months: set[tuple[int, int]]) -> list[dict]:
    """Walk Capella STAC `by-datetime/<year>/<month>/` catalog."""
    scenes = []
    for year, month in sorted(months):
        url = f"{CAPELLA_BASE}/capella-open-data-by-datetime/{year}/{year}-{month:02d}/catalog.json"
        cat = fetch_json(url)
        if not cat:
            print(f"  Capella {year}-{month:02d}: catalog missing", flush=True)
            continue
        item_links = [l for l in cat.get("links", []) if l.get("rel") == "item"]
        print(f"  Capella {year}-{month:02d}: {len(item_links)} items", flush=True)
        for il in item_links:
            href = il.get("href", "")
            if href.startswith("./"):
                href = url.rsplit("/", 1)[0] + "/" + href[2:]
            item = fetch_json(href)
            if item and item.get("type") == "Feature":
                scenes.append(("capella", item))
    return scenes


def main() -> int:
    # Build set of (year, month) tuples covering all incident windows ± WINDOW_DAYS
    months_needed: set[tuple[int, int]] = set()
    for _, _, _, _, ds in INCIDENTS:
        d = datetime.fromisoformat(ds).date()
        for off in (-WINDOW_DAYS, 0, WINDOW_DAYS):
            dd = d + timedelta(days=off)
            months_needed.add((dd.year, dd.month))

    print(f"Searching Umbra for {len(months_needed)} months...", flush=True)
    umbra_scenes = walk_umbra(months_needed)
    print(f"\nSearching Capella for {len(months_needed)} months...", flush=True)
    capella_scenes = walk_capella(months_needed)

    all_scenes = umbra_scenes + capella_scenes
    print(f"\nTotal scenes fetched: {len(all_scenes)}", flush=True)

    # Filter to Baltic bbox and match to incidents
    out_rows: list[dict] = []
    for source, item in all_scenes:
        scene_bbox = item.get("bbox") or [0, 0, 0, 0]
        if len(scene_bbox) < 4 or not bbox_intersects(scene_bbox, BBOX):
            continue
        props = item.get("properties", {}) or {}
        scene_dt_str = props.get("datetime", "")
        try:
            scene_dt = datetime.fromisoformat(scene_dt_str.replace("Z", "+00:00")).date()
        except ValueError:
            scene_dt = None
        # Match to nearest incident
        for inc_id, name, lat, lon, ds in INCIDENTS:
            inc_d = datetime.fromisoformat(ds).date()
            if scene_dt and abs((scene_dt - inc_d).days) <= WINDOW_DAYS:
                # Also check spatial proximity (incident point inside scene bbox)
                if scene_bbox[0] <= lon <= scene_bbox[2] and scene_bbox[1] <= lat <= scene_bbox[3]:
                    out_rows.append({
                        "incident_id": inc_id,
                        "incident_name": name,
                        "source": source,
                        "scene_id": item.get("id", ""),
                        "scene_datetime": scene_dt_str,
                        "bbox_min_lon": scene_bbox[0],
                        "bbox_min_lat": scene_bbox[1],
                        "bbox_max_lon": scene_bbox[2],
                        "bbox_max_lat": scene_bbox[3],
                        "self_href": next((l["href"] for l in item.get("links", []) if l.get("rel") == "self"), ""),
                    })

    out_csv = Path("data/reference/commercial_sar_scenes.csv")
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "incident_id", "incident_name", "source", "scene_id", "scene_datetime",
            "bbox_min_lon", "bbox_min_lat", "bbox_max_lon", "bbox_max_lat", "self_href",
        ])
        w.writeheader()
        for r in out_rows:
            w.writerow(r)
    print(f"\nWrote {len(out_rows)} Baltic-intersecting scenes -> {out_csv}", flush=True)
    # Per-incident counts
    from collections import Counter
    c = Counter((r["incident_id"], r["source"]) for r in out_rows)
    for (inc_id, src), n in sorted(c.items()):
        print(f"  {inc_id} {src:8s} {n}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
