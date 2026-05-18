"""Fetch additional OSM seamark layers — navigational context for the Baltic.

Adds layers beyond the §5.2 criticality set:
  - Traffic separation schemes (TSS)
  - Restricted military areas
  - Fishing grounds
  - Anchorages
  - Lighthouses (major)
  - Buoys / beacons (cardinal/lateral/special)
  - Wreck markers

License: ODbL 1.0 (OSM)
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

BBOX = (52.0, 9.0, 66.0, 30.0)  # S, W, N, E

OUT_DIR = Path("data/geo")
OUT_DIR.mkdir(parents=True, exist_ok=True)

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

LAYERS: dict[str, str] = {
    "tss": """
(
  way["seamark:type"~"separation_zone|separation_line|separation_lane|separation_boundary|separation_crossing|separation_roundabout"];
);
""",
    "restricted_areas": """
(
  way["seamark:type"="restricted_area"];
  relation["seamark:type"="restricted_area"];
  way["military"="restricted_area"];
);
""",
    "anchorages": """
(
  node["seamark:type"="anchorage"];
  way["seamark:type"="anchorage"];
  relation["seamark:type"="anchorage"];
);
""",
    "lighthouses": """
(
  node["seamark:type"="light_major"];
  node["seamark:type"="light_minor"];
  node["man_made"="lighthouse"];
);
""",
    "buoys": """
(
  node["seamark:type"~"buoy_cardinal|buoy_lateral|buoy_safe_water|buoy_special_purpose|buoy_isolated_danger"];
);
""",
    "wrecks": """
(
  node["seamark:type"="wreck"];
  way["seamark:type"="wreck"];
);
""",
    "fishing_grounds": """
(
  way["seamark:type"="fishing_ground"];
  relation["seamark:type"="fishing_ground"];
);
""",
    "fairways": """
(
  way["seamark:type"="fairway"];
);
""",
}


def overpass(query: str, timeout: int = 180) -> dict | None:
    for ep in ENDPOINTS:
        try:
            r = requests.post(
                ep,
                data={"data": query},
                timeout=timeout + 30,
                headers={"User-Agent": "edth2026-baltic-prep/0.1"},
            )
            r.raise_for_status()
            return r.json()
        except (requests.exceptions.RequestException, json.JSONDecodeError) as ex:
            print(f"    {ep} failed: {ex}", flush=True)
            time.sleep(2)
    return None


def to_geojson(elements):
    feats = []
    for e in elements:
        tags = e.get("tags", {}) or {}
        if e["type"] == "node":
            feats.append({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [e["lon"], e["lat"]]},
                "properties": {**tags, "osm_id": f"node/{e['id']}"},
            })
        elif e["type"] == "way" and "geometry" in e:
            coords = [[p["lon"], p["lat"]] for p in e["geometry"]]
            geom_type = "LineString"
            if len(coords) >= 4 and coords[0] == coords[-1] and any(
                k in tags for k in ("seamark:type", "military", "landuse")
            ):
                geom_type = "Polygon"
                coords = [coords]
            feats.append({
                "type": "Feature",
                "geometry": {"type": geom_type, "coordinates": coords},
                "properties": {**tags, "osm_id": f"way/{e['id']}"},
            })
    return feats


def fetch_layer(name: str, body: str) -> None:
    print(f"\n[{name}]", flush=True)
    bbox = f"{BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]}"
    q = f"[out:json][timeout:180][bbox:{bbox}];\n{body}\nout geom;"
    data = overpass(q)
    if not data:
        print(f"  all mirrors failed", flush=True)
        return
    feats = to_geojson(data.get("elements", []))
    gj = {
        "type": "FeatureCollection",
        "metadata": {
            "source": "OpenStreetMap (Overpass)",
            "license": "ODbL 1.0",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "bbox_south_west_north_east": list(BBOX),
            "feature_count": len(feats),
        },
        "features": feats,
    }
    out = OUT_DIR / f"osm_{name}.geojson"
    out.write_text(json.dumps(gj, separators=(",", ":")), encoding="utf-8")
    print(f"  -> {out}  {len(feats)} features  {out.stat().st_size//1024} KB", flush=True)


def main() -> int:
    for name, body in LAYERS.items():
        try:
            fetch_layer(name, body)
        except Exception as ex:
            print(f"  ERROR: {ex}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
