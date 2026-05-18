"""Fetch bathymetry (sea floor depths) for the Baltic.

Tries GMRT (Global Multi-Resolution Topography, free, no auth) first,
falls back to EMODnet Bathymetry WCS if GMRT is unavailable.

License:
  - GMRT: free for non-commercial use; cite Ryan et al. (2009)
  - EMODnet Bathymetry: CC-BY 4.0

Output:
  data/geo/bathymetry_baltic.nc   (NetCDF grid)
  data/geo/bathymetry_baltic.tif  (GeoTIFF if conversion possible)
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

OUT_DIR = Path("data/geo")
OUT_DIR.mkdir(parents=True, exist_ok=True)

BBOX_NORTH = 66
BBOX_SOUTH = 52
BBOX_EAST = 30
BBOX_WEST = 9

GMRT_URL = "https://www.gmrt.org/services/GridServer"
EMODNET_BATHY_WCS = "https://ows.emodnet-bathymetry.eu/wcs"


def try_gmrt(out_path: Path) -> bool:
    print(f"[GMRT] requesting bathymetry grid...")
    params = {
        "north": BBOX_NORTH,
        "south": BBOX_SOUTH,
        "east": BBOX_EAST,
        "west": BBOX_WEST,
        "layer": "topo",
        "format": "netcdf",
        "resolution": "high",
    }
    try:
        with requests.get(GMRT_URL, params=params, stream=True, timeout=600,
                          headers={"User-Agent": "edth2026-baltic-prep/0.1"}) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
        size_mb = out_path.stat().st_size / 1_048_576
        print(f"  -> {out_path}  {size_mb:.1f} MB")
        return size_mb > 0.01  # at least 10 KB
    except requests.exceptions.RequestException as ex:
        print(f"  failed: {ex}")
        return False


def try_emodnet_wcs(out_path: Path) -> bool:
    print(f"[EMODnet Bathymetry WCS] requesting coverage...")
    # WCS 2.0.1 GetCoverage request
    params = {
        "service": "WCS",
        "version": "2.0.1",
        "request": "GetCoverage",
        "coverageid": "emodnet:mean",
        "format": "image/tiff",
        "subset": [
            f"Lat({BBOX_SOUTH},{BBOX_NORTH})",
            f"Long({BBOX_WEST},{BBOX_EAST})",
        ],
    }
    try:
        with requests.get(EMODNET_BATHY_WCS, params=params, stream=True, timeout=600,
                          headers={"User-Agent": "edth2026-baltic-prep/0.1"}) as r:
            print(f"  HTTP {r.status_code}, content-type {r.headers.get('content-type')}")
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
        size_mb = out_path.stat().st_size / 1_048_576
        print(f"  -> {out_path}  {size_mb:.1f} MB")
        return size_mb > 0.01
    except requests.exceptions.RequestException as ex:
        print(f"  failed: {ex}")
        return False


def main() -> int:
    nc_path = OUT_DIR / "bathymetry_baltic.nc"
    tif_path = OUT_DIR / "bathymetry_baltic.tif"
    if not nc_path.exists() or nc_path.stat().st_size < 10 * 1024:
        ok = try_gmrt(nc_path)
        if not ok:
            print("  GMRT failed, trying EMODnet WCS as TIFF")
            try_emodnet_wcs(tif_path)
    else:
        print(f"  cache hit: {nc_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
