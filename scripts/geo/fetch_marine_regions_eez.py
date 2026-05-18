"""Fetch Maritime Boundaries / EEZ from Marine Regions (Flanders Marine Institute, VLIZ).

License: CC-BY 4.0. Attribution: "Flanders Marine Institute (VLIZ); Maritime Boundaries Geodatabase".

We download the full World EEZ shapefile zip (~120 MB), extract, filter to Baltic
states + adjacent EU countries, and convert to GeoJSON for the geo/ directory.
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
RAW_DIR = OUT_DIR / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

EEZ_URL = "https://www.marineregions.org/download_file.php?name=World_EEZ_v12.zip"

BALTIC_COUNTRIES = {
    "Denmark", "Sweden", "Finland", "Estonia", "Latvia", "Lithuania",
    "Poland", "Germany", "Russia",
    # adjacent
    "Norway", "United Kingdom",
}


def main() -> int:
    print("[Marine Regions EEZ]")
    print(f"  downloading {EEZ_URL}")
    zip_path = RAW_DIR / "marine_regions_eez_v12.zip"
    if not zip_path.exists():
        with requests.get(EEZ_URL, stream=True, timeout=600,
                          headers={"User-Agent": "edth2026-baltic-prep/0.1"}) as r:
            r.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
    mb = zip_path.stat().st_size / 1_048_576
    print(f"  zip: {mb:.0f} MB")

    # Extract to a temp dir
    extract_dir = RAW_DIR / "marine_regions_extracted"
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_dir)
    print(f"  extracted to {extract_dir}")

    # Find the main shapefile
    shp_files = list(extract_dir.rglob("*.shp"))
    if not shp_files:
        print("  ERROR: no .shp file in archive", file=sys.stderr)
        return 1
    main_shp = next((s for s in shp_files if "boundaries" not in s.name.lower() and "joined" not in s.name.lower() and "lines" not in s.name.lower()), shp_files[0])
    print(f"  using {main_shp.name}")

    gdf = gpd.read_file(main_shp)
    print(f"  loaded {len(gdf)} EEZ polygons")
    print(f"  columns: {list(gdf.columns)[:10]}")

    # Filter to Baltic + adjacent countries
    country_col = next((c for c in ("SOVEREIGN1", "Sovereign1", "TERRITORY1", "Territory1", "GEONAME")
                        if c in gdf.columns), None)
    if not country_col:
        print(f"  ERROR: no country column found in {list(gdf.columns)}", file=sys.stderr)
        return 1
    baltic = gdf[gdf[country_col].isin(BALTIC_COUNTRIES)].copy()
    print(f"  filtered to {len(baltic)} Baltic-region EEZ polygons")

    # Crop bbox roughly to Baltic + adjacent
    baltic = baltic.cx[5:35, 50:70]
    print(f"  after Baltic-area cx clip: {len(baltic)}")

    # Reproject to WGS84 if needed
    if baltic.crs and baltic.crs.to_epsg() != 4326:
        baltic = baltic.to_crs(epsg=4326)

    out = OUT_DIR / "marine_regions_eez_baltic.geojson"
    # Add metadata wrapping (geopandas writes plain GeoJSON; we wrap manually)
    feats_json = json.loads(baltic.to_json())
    feats_json["metadata"] = {
        "source": "Marine Regions / Flanders Marine Institute (VLIZ), World EEZ v12",
        "license": "CC-BY 4.0",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "feature_count": len(feats_json.get("features", [])),
        "country_filter": sorted(BALTIC_COUNTRIES),
    }
    out.write_text(json.dumps(feats_json, indent=1), encoding="utf-8")
    print(f"  -> {out}  {out.stat().st_size//1024} KB")

    # Cleanup extracted shapefile to save disk (keep the zip for reproducibility)
    import shutil
    shutil.rmtree(extract_dir)
    print(f"  cleaned up {extract_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
