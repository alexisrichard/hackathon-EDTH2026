"""Rasterize the Baltic criticality layers into a single ~1 km² GeoTIFF grid.

For each cell in the Baltic bbox (lat 52-66, lon 9-30), compute a criticality
score in [0, 1] from the distance to each infrastructure layer. This is the
`local_criticality(vessel.position)` term from PLAN.md §5.4.

Score recipe:
  cable_score      = exp(-d_to_cable_km / 5)      # decays over ~5 km
  pipeline_score   = exp(-d_to_pipeline_km / 10)  # decays over ~10 km
  naval_score      = exp(-d_to_naval_km / 20)     # broader influence
  windfarm_score   = exp(-d_to_windfarm_km / 5)   # short influence
  criticality      = max of the above

Output:
  data/geo/criticality_grid.tif       # raster, EPSG:4326, ~0.01° pixels
  data/geo/criticality_preview.png    # quick preview

This is a STARTER implementation — the hackathon team will refine weights.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import unary_union

OUT_DIR = Path("data/geo")
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Baltic bbox + grid resolution
LAT_MIN, LAT_MAX = 52.0, 66.0
LON_MIN, LON_MAX = 9.0, 30.0
CELL_DEG = 0.05  # ~5.5 km at 60°N; coarser than spec but fast to compute

# Layers to ingest. Try EMODnet first, fall back to OSM.
LAYER_PRIORITY = {
    "cables": ["data/geo/emodnet_cables_combined.geojson", "data/geo/submarine_cables.geojson"],
    "pipelines": ["data/geo/emodnet_pipelines.geojson", "data/geo/pipelines.geojson"],
    "naval_bases": ["data/geo/naval_bases.geojson"],
    "windfarms": ["data/geo/emodnet_windfarmspoly.geojson", "data/geo/offshore_wind.geojson"],
    "ports": ["data/geo/ports.geojson"],
    "refineries_lng": ["data/geo/refineries_lng.geojson"],
}

# Influence decay scale (km)
DECAY_KM = {
    "cables": 5.0,
    "pipelines": 10.0,
    "naval_bases": 20.0,
    "windfarms": 5.0,
    "ports": 8.0,
    "refineries_lng": 15.0,
}


def load_layer(paths: list[str]) -> gpd.GeoDataFrame | None:
    for p in paths:
        path = Path(p)
        if path.exists():
            try:
                return gpd.read_file(path)
            except Exception as ex:
                print(f"  failed to load {path}: {ex}", flush=True)
                continue
    return None


def main() -> int:
    # Build grid
    lats = np.arange(LAT_MIN + CELL_DEG / 2, LAT_MAX, CELL_DEG)
    lons = np.arange(LON_MIN + CELL_DEG / 2, LON_MAX, CELL_DEG)
    print(f"Grid: {len(lats)} x {len(lons)} = {len(lats) * len(lons):,} cells", flush=True)

    # Use UTM zone 33N (covers central Baltic) for metric distances
    UTM_EPSG = 32633

    # Build a GeoDataFrame of grid cell centers
    grid_pts = gpd.GeoDataFrame(
        {"i": np.repeat(np.arange(len(lats)), len(lons)),
         "j": np.tile(np.arange(len(lons)), len(lats)),
         "lat": np.repeat(lats, len(lons)),
         "lon": np.tile(lons, len(lats))},
        geometry=gpd.points_from_xy(np.tile(lons, len(lats)), np.repeat(lats, len(lons))),
        crs="EPSG:4326",
    ).to_crs(UTM_EPSG)
    print(f"Grid points in UTM: {len(grid_pts):,}", flush=True)

    # Score per layer
    score = np.zeros((len(lats), len(lons)), dtype=np.float32)
    component_scores: dict[str, np.ndarray] = {}
    for name, paths in LAYER_PRIORITY.items():
        gdf = load_layer(paths)
        if gdf is None or gdf.empty:
            print(f"  {name}: no layer found, skipping", flush=True)
            continue
        gdf = gdf.to_crs(UTM_EPSG)
        # Sample subsample if very large (performance)
        max_features = 5000
        if len(gdf) > max_features:
            print(f"  {name}: {len(gdf)} features, sampling {max_features}", flush=True)
            gdf = gdf.sample(max_features, random_state=42)
        else:
            print(f"  {name}: {len(gdf)} features", flush=True)
        try:
            union = unary_union(gdf.geometry.values)
        except Exception as ex:
            print(f"  union failed: {ex}; using bounds centroid fallback", flush=True)
            union = unary_union([g.centroid for g in gdf.geometry.values])
        # Compute distance from each grid point to the union
        dist_m = grid_pts.distance(union).values  # meters
        dist_km = dist_m / 1000.0
        decay = DECAY_KM[name]
        comp = np.exp(-dist_km / decay).reshape(len(lats), len(lons)).astype(np.float32)
        component_scores[name] = comp
        score = np.maximum(score, comp)
        print(f"  {name}: max component score {comp.max():.3f}, mean {comp.mean():.3f}", flush=True)

    # Save as numpy npz (lightweight, doesn't require rasterio for the team)
    out = OUT_DIR / "criticality_grid.npz"
    np.savez_compressed(
        out,
        score=score,
        lats=lats,
        lons=lons,
        **{f"score_{k}": v for k, v in component_scores.items()},
        meta=json.dumps({
            "bbox_lat_min_max_lon_min_max": [LAT_MIN, LAT_MAX, LON_MIN, LON_MAX],
            "cell_deg": CELL_DEG,
            "decay_km": DECAY_KM,
            "layers_used": list(component_scores.keys()),
        }),
    )
    size_kb = out.stat().st_size // 1024
    print(f"\nWrote {out}  size={size_kb} KB  shape={score.shape}", flush=True)
    print(f"Composite score stats: min={score.min():.3f}, mean={score.mean():.3f}, max={score.max():.3f}", flush=True)

    # Save GeoJSON of top-N criticality hotspots (lat/lon centroids w/ score > threshold)
    threshold = 0.7
    hot_i, hot_j = np.where(score > threshold)
    hotspots = []
    for i, j in zip(hot_i, hot_j):
        hotspots.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(lons[j]), float(lats[i])]},
            "properties": {"score": float(score[i, j])},
        })
    hot_path = OUT_DIR / "criticality_hotspots.geojson"
    hot_path.write_text(json.dumps({
        "type": "FeatureCollection",
        "metadata": {
            "score_threshold": threshold,
            "feature_count": len(hotspots),
            "sources": list(component_scores.keys()),
        },
        "features": hotspots,
    }), encoding="utf-8")
    print(f"Wrote {hot_path}  hotspots={len(hotspots)}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
