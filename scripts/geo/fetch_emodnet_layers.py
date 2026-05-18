"""Fetch additional Baltic-Sea criticality layers from EMODnet Human Activities
(CC-BY 4.0) — higher-quality than OSM for offshore cables/pipelines/wind farms.

Outputs:
  data/geo/emodnet_pipelines.geojson
  data/geo/emodnet_windfarms.geojson
  data/geo/emodnet_cables_combined.geojson  (union of all national cable layers)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

OUT_DIR = Path("data/geo")
OUT_DIR.mkdir(parents=True, exist_ok=True)

BBOX = (9.0, 52.0, 30.0, 66.0)  # WFS bbox is min_lon, min_lat, max_lon, max_lat
WFS = "https://ows.emodnet-humanactivities.eu/wfs"
UA = {"User-Agent": "edth2026-baltic-prep/0.1"}

# Single layers worth pulling in their own right
SIMPLE_LAYERS = [
    ("pipelines", "emodnet:pipelines"),
    ("windfarmspoly", "emodnet:windfarmspoly"),
    ("windfarms_point", "emodnet:windfarms"),
]

# National cable layers — merge into one Baltic file
CABLE_LAYERS = [
    "emodnet:bshcontiscables",  # Germany BSH
    "emodnet:rijkscables",       # Netherlands
    "emodnet:pcablesbshcontis",  # Germany (alt)
    "emodnet:pcablesrijks",      # NL (alt)
    "emodnet:pcablesnve",        # Norway NVE
]


def wfs_fetch(layer: str, timeout: int = 120) -> dict | None:
    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": layer,
        "outputFormat": "application/json",
        "bbox": f"{BBOX[0]},{BBOX[1]},{BBOX[2]},{BBOX[3]},EPSG:4326",
    }
    r = requests.get(WFS, params=params, timeout=timeout, headers=UA)
    if r.status_code != 200:
        print(f"  {layer}: HTTP {r.status_code}", flush=True)
        return None
    try:
        return r.json()
    except json.JSONDecodeError as ex:
        print(f"  {layer}: JSON parse failed: {ex}", flush=True)
        return None


def save_layer(name: str, layer: str) -> None:
    print(f"[{name}] -> {layer}")
    gj = wfs_fetch(layer)
    if not gj:
        return
    feats = gj.get("features", [])
    # Add metadata
    gj["metadata"] = {
        "source": f"EMODnet Human Activities ({layer})",
        "license": "CC-BY 4.0",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "bbox_min_lon_min_lat_max_lon_max_lat": list(BBOX),
        "feature_count": len(feats),
    }
    out = OUT_DIR / f"emodnet_{name}.geojson"
    out.write_text(json.dumps(gj, indent=1), encoding="utf-8")
    print(f"  -> {out}  {len(feats)} features  {out.stat().st_size//1024} KB", flush=True)


def merge_cables() -> None:
    print(f"[cables_combined] merging {len(CABLE_LAYERS)} national cable layers")
    all_feats = []
    sources_used = []
    for layer in CABLE_LAYERS:
        gj = wfs_fetch(layer)
        if not gj:
            continue
        feats = gj.get("features", [])
        for f in feats:
            f["properties"] = f.get("properties", {}) or {}
            f["properties"]["_emodnet_layer"] = layer
            all_feats.append(f)
        sources_used.append(layer)
        print(f"  {layer}: {len(feats)} features", flush=True)
    merged = {
        "type": "FeatureCollection",
        "metadata": {
            "source": "EMODnet Human Activities (multiple national cable layers merged)",
            "layers": sources_used,
            "license": "CC-BY 4.0",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "bbox_min_lon_min_lat_max_lon_max_lat": list(BBOX),
            "feature_count": len(all_feats),
        },
        "features": all_feats,
    }
    out = OUT_DIR / "emodnet_cables_combined.geojson"
    out.write_text(json.dumps(merged, indent=1), encoding="utf-8")
    print(f"  -> {out}  {len(all_feats)} total features  {out.stat().st_size//1024} KB", flush=True)


def main() -> int:
    for name, layer in SIMPLE_LAYERS:
        save_layer(name, layer)
    merge_cables()
    return 0


if __name__ == "__main__":
    sys.exit(main())
