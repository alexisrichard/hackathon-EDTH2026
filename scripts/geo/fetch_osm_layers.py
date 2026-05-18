"""Fetch Baltic-Sea criticality layers from OpenStreetMap via Overpass API.

Outputs one GeoJSON per layer in data/geo/. These are small (<50 MB total)
and intentionally version-controlled so the team can clone-and-go.

Run:
    python scripts/geo/fetch_osm_layers.py [layer_name ...]

With no args, fetches all layers. With layer names, fetches only those.
Safe to re-run; each call overwrites the previous output.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# Baltic bounding box: Overpass uses (south, west, north, east)
BBOX = (52.0, 9.0, 66.0, 30.0)

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

OUT_DIR = Path("data/geo")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def overpass(query: str, timeout: int = 180) -> dict:
    """POST a query to Overpass, retrying across mirrors on transient failure."""
    last_err: Exception | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            r = requests.post(
                endpoint,
                data={"data": query},
                timeout=timeout + 30,
                headers={"User-Agent": "edth2026-baltic-prep/0.1 (alexisrichard@github)"},
            )
            r.raise_for_status()
            return r.json()
        except (requests.exceptions.RequestException, json.JSONDecodeError) as ex:
            print(f"    {endpoint} failed: {ex}; trying next mirror...", flush=True)
            last_err = ex
            time.sleep(2)
    raise RuntimeError(f"All Overpass mirrors failed; last error: {last_err}")


def way_geometry(element: dict) -> tuple[str, list]:
    """Return ('LineString' | 'Polygon', coords) for an Overpass `way` with `out geom`."""
    coords = [[p["lon"], p["lat"]] for p in element.get("geometry", [])]
    if len(coords) >= 4 and coords[0] == coords[-1]:
        tags = element.get("tags", {})
        area_tags = ("building", "landuse", "harbour", "military", "man_made", "amenity", "industrial", "natural")
        if any(t in tags for t in area_tags):
            return "Polygon", [coords]
    return "LineString", coords


def to_geojson(elements: list[dict], source_note: str) -> dict:
    features = []
    for e in elements:
        tags = e.get("tags") or {}
        if e["type"] == "node":
            geom = {"type": "Point", "coordinates": [e["lon"], e["lat"]]}
            osm_id = f"node/{e['id']}"
        elif e["type"] == "way" and "geometry" in e:
            gt, coords = way_geometry(e)
            geom = {"type": gt, "coordinates": coords}
            osm_id = f"way/{e['id']}"
        else:
            continue
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {**tags, "osm_id": osm_id},
        })
    return {
        "type": "FeatureCollection",
        "metadata": {
            "source": source_note,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "bbox_south_west_north_east": list(BBOX),
            "feature_count": len(features),
        },
        "features": features,
    }


def fetch_layer(name: str, ql_body: str) -> None:
    print(f"\n[{name}]", flush=True)
    bbox = f"{BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]}"
    query = f"[out:json][timeout:180][bbox:{bbox}];\n{ql_body}\nout geom;"
    try:
        data = overpass(query)
    except Exception as ex:
        print(f"  ERROR: {ex}", flush=True)
        return
    gj = to_geojson(data.get("elements", []), source_note="OpenStreetMap (Overpass)")
    out = OUT_DIR / f"{name}.geojson"
    out.write_text(json.dumps(gj, indent=1), encoding="utf-8")
    print(
        f"  {gj['metadata']['feature_count']:>6} features  "
        f"{out.stat().st_size // 1024:>5} KB  -> {out}",
        flush=True,
    )


LAYERS: dict[str, str] = {
    # OSM cable_submarine tag covers telecom AND power; we keep both here and
    # subset to power-only in submarine_power_cables for convenience.
    "submarine_cables": """
(
  way["seamark:type"="cable_submarine"];
  way["submarine"="yes"]["communication"];
  way["submarine"="yes"]["communication:cable"];
);
""",
    "submarine_power_cables": """
(
  way["submarine"="yes"]["power"="cable"];
  way["power"="cable"]["location"="underwater"];
);
""",
    # Pipelines: keep both onshore + offshore in the bbox; filter on `submarine`
    # or `location=underwater` downstream.
    "pipelines": """
(
  way["man_made"="pipeline"]["location"="underwater"];
  way["man_made"="pipeline"]["seamark:type"="pipeline_submarine"];
  way["man_made"="pipeline"]["substance"~"gas|oil|petroleum|naphtha|lng",i];
);
""",
    "ports": """
(
  node["harbour"="yes"];
  way["harbour"="yes"];
  relation["harbour"="yes"];
  way["landuse"="port"];
  way["landuse"="harbour"];
  way["industrial"="port"];
  node["seamark:type"="harbour"];
);
""",
    "naval_bases": """
(
  node["military"="naval_base"];
  way["military"="naval_base"];
  relation["military"="naval_base"];
);
""",
    # Tightened: drop storage_tank (1988 false-positives from farm fuel tanks).
    "refineries_lng": """
(
  way["man_made"="works"]["product"~"oil|petroleum|refined products|fuel|gas|lng|petrochemical",i];
  way["industrial"="oil"];
  way["industrial"="petrochemical"];
  way["industrial"="refinery"];
  way["amenity"="lng_terminal"];
  node["industrial"="terminal"]["product"~"lng|gas|oil",i];
  way["industrial"="terminal"]["product"~"lng|gas|oil",i];
);
""",
    "offshore_platforms": """
(
  node["man_made"="offshore_platform"];
  way["man_made"="offshore_platform"];
);
""",
    # Offshore wind: target wind farms as relations/areas. Baltic-specific tags.
    "offshore_wind": """
(
  way["seamark:type"="wind_farm"];
  relation["seamark:type"="wind_farm"];
  way["site"="wind_farm"];
  relation["site"="wind_farm"];
  way["power"="plant"]["plant:source"="wind"];
  relation["power"="plant"]["plant:source"="wind"];
  way["landuse"="wind_farm"];
);
""",
}


def main(argv: list[str]) -> int:
    selected = argv[1:] if len(argv) > 1 else list(LAYERS.keys())
    bad = [s for s in selected if s not in LAYERS]
    if bad:
        print(f"Unknown layer(s): {bad}\nAvailable: {list(LAYERS.keys())}", file=sys.stderr)
        return 2
    print(f"Baltic criticality layers — OSM Overpass")
    print(f"  bbox (S,W,N,E): {BBOX}")
    print(f"  output:         {OUT_DIR.resolve()}")
    print(f"  layers:         {selected}")
    for name in selected:
        fetch_layer(name, LAYERS[name])
    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
