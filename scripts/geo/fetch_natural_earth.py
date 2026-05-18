"""Fetch Natural Earth vector basemap layers (Public Domain, CC0).

Useful for background context: country borders, coastlines, populated places,
roads. All small (<50 MB total). Direct downloads from naturalearthdata.com.

Outputs:
  data/geo/ne_countries_50m.geojson
  data/geo/ne_coastline_10m.geojson
  data/geo/ne_ports_10m.geojson  (if available)
"""
from __future__ import annotations

import json
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import requests

OUT_DIR = Path("data/geo")
OUT_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR = OUT_DIR / "raw" / "natural_earth"
RAW_DIR.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "edth2026-baltic-prep/0.1"}

LAYERS = [
    # (output_name, NE category, NE filename without .zip)
    ("countries_50m",  "cultural", "ne_50m_admin_0_countries"),
    ("coastline_10m",  "physical", "ne_10m_coastline"),
    ("ports_10m",      "cultural", "ne_10m_ports"),
    ("ocean_10m",      "physical", "ne_10m_ocean"),
    ("rivers_10m",     "physical", "ne_10m_rivers_lake_centerlines"),
    ("urban_areas_10m","cultural", "ne_10m_urban_areas"),
]


def fetch_zip(category: str, name: str) -> Path | None:
    url = f"https://naciscdn.org/naturalearth/10m/{category}/{name}.zip"
    if "_50m" in name:
        url = f"https://naciscdn.org/naturalearth/50m/{category}/{name}.zip"
    print(f"  {url}", flush=True)
    out = RAW_DIR / f"{name}.zip"
    if out.exists() and out.stat().st_size > 0:
        return out
    try:
        with requests.get(url, stream=True, timeout=120, headers=UA) as r:
            r.raise_for_status()
            with open(out, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
        return out
    except requests.exceptions.RequestException as ex:
        print(f"    failed: {ex}", flush=True)
        return None


def process_layer(name: str, category: str, ne_name: str) -> None:
    print(f"\n[{name}]", flush=True)
    zip_path = fetch_zip(category, ne_name)
    if not zip_path:
        return
    extract_dir = RAW_DIR / ne_name
    extract_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    shp_files = list(extract_dir.glob("*.shp"))
    if not shp_files:
        print(f"  no .shp in archive", flush=True)
        return
    gdf = gpd.read_file(shp_files[0])
    # Clip to Baltic-wide bbox
    gdf = gdf.cx[5:35, 50:70]
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    out = OUT_DIR / f"ne_{name}.geojson"
    data = json.loads(gdf.to_json())
    data["metadata"] = {
        "source": f"Natural Earth ({ne_name})",
        "license": "Public Domain (CC0)",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "feature_count": len(data.get("features", [])),
    }
    out.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"  -> {out}  {len(data['features'])} features  {out.stat().st_size//1024} KB", flush=True)


def main() -> int:
    for name, cat, ne in LAYERS:
        try:
            process_layer(name, cat, ne)
        except Exception as ex:
            print(f"  ERROR processing {name}: {ex}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
