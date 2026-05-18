"""Fetch HELCOM Baltic Sea vector datasets via ArcGIS REST API.

HELCOM (Helsinki Commission) is the regional Baltic environmental authority.
Their MADS service exposes Baltic-specific shipping/fisheries/biodiversity data.

Service catalog: https://maps.helcom.fi/arcgis/rest/services/

License: HELCOM data are generally free to use with attribution.

Fetched layers (Feature Layers only — rasters skipped):
  - Shipping accidents
  - Detected oil and other spills
  - AIS passage line crossings by ship type
  - Dredging and disposal sites
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

OUT_DIR = Path("data/geo")
OUT_DIR.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "edth2026-baltic-prep/0.1"}

# (output_name, service, layer_id)
LAYERS = [
    ("helcom_shipping_accidents",        "MADS/Shipping/MapServer",        325),
    ("helcom_detected_spills",           "MADS/Shipping/MapServer",        323),
    ("helcom_ais_passage_crossings",     "MADS/Shipping/MapServer",        0),
    ("helcom_dredging_sites_points",     "MADS/Human_Activities/MapServer", 169),
    ("helcom_dredging_sites_areas",      "MADS/Human_Activities/MapServer", 170),
    ("helcom_disposal_sites_areas",      "MADS/Human_Activities/MapServer", 172),
    ("helcom_fishing_intensity_total_2016_2021", "MADS/Human_Activities/MapServer", 163),
]

BASE = "https://maps.helcom.fi/arcgis/rest/services"


def fetch_layer(out_name: str, service: str, layer_id: int) -> None:
    print(f"\n[{out_name}] -> {service}/{layer_id}", flush=True)
    url = f"{BASE}/{service}/{layer_id}/query"
    params = {
        "where": "1=1",
        "outFields": "*",
        "f": "geojson",
        "outSR": 4326,
        "returnGeometry": "true",
        "resultRecordCount": 50000,
    }
    try:
        r = requests.get(url, params=params, timeout=180, headers=UA)
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}: {r.text[:200]}", flush=True)
            return
        try:
            data = r.json()
        except json.JSONDecodeError:
            print(f"  Non-JSON response: {r.text[:200]}", flush=True)
            return
    except requests.exceptions.RequestException as ex:
        print(f"  failed: {ex}", flush=True)
        return

    if "error" in data:
        print(f"  ArcGIS error: {data['error']}", flush=True)
        return

    feats = data.get("features", [])
    if not feats:
        print(f"  (no features returned)", flush=True)
        return

    # Wrap with metadata
    gj = {
        "type": "FeatureCollection",
        "metadata": {
            "source": f"HELCOM MADS / {service} layer {layer_id}",
            "license": "Free with attribution (HELCOM)",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "feature_count": len(feats),
        },
        "features": feats,
    }
    out = OUT_DIR / f"{out_name}.geojson"
    out.write_text(json.dumps(gj, separators=(",", ":")), encoding="utf-8")
    print(f"  -> {out}  {len(feats)} features  {out.stat().st_size//1024} KB", flush=True)


def main() -> int:
    for out_name, service, layer_id in LAYERS:
        try:
            fetch_layer(out_name, service, layer_id)
        except Exception as ex:
            print(f"  ERROR: {ex}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
