"""Compile data/geo sources into web-sized layers for the frontend map.

Outputs (committed, loaded by the V1 UI at runtime):
  frontend/public/data/jurisdiction.json   EEZ + 12nm territorial-sea boundary lines
  frontend/public/data/infra_lines.json    cables + pipelines (scored lines)
  frontend/public/data/poi.json            discrete points of interest (scored)

V1 STRATEGIC SCORING ("heat score", 0-1) — class-based, deliberately simple.
The per-feature `s` is the seed for the unified criticality surface (PLAN §5.2);
tune the weights here and rebuild. @Côme @Gabriel: adjust freely.

Usage:  python scripts/geo/build_web_layers.py
Needs:  data/geo/* (committed) + marine_regions_{eez_baltic,12nm}.geojson
        (large, S3:  python scripts/common/sync_from_s3.py geo)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[2]
GEO = ROOT / "data" / "geo"
OUT = ROOT / "frontend" / "public" / "data"
OUT.mkdir(parents=True, exist_ok=True)

# Theatre: North Sea + Baltic
THEATRE = box(-2.0, 50.0, 32.0, 67.0)

# ---- v1 strategic weights (the knob to tune) --------------------------------
SCORES = {
    "telecom_cable": 0.95,
    "power_cable":   0.95,
    "pipeline":      0.90,
    "chokepoint":    0.90,
    "naval_base":    0.85,
    "energy_terminal": 0.80,
    "port":          0.65,
    "windfarm":      0.60,
    "platform":      0.60,
    "anchorage":     0.40,
    "lighthouse":    0.30,
}

PREC = 4  # coordinate decimals (~11 m)


def round_coords(obj, prec: int):
    """Recursively round coordinate arrays in a GeoJSON geometry dict."""
    if isinstance(obj, float):
        return round(obj, prec)
    if isinstance(obj, list):
        return [round_coords(o, prec) for o in obj]
    return obj


def geom_dict(geom, prec: int = PREC) -> dict:
    g = json.loads(gpd.GeoSeries([geom]).to_json())["features"][0]["geometry"]
    g["coordinates"] = round_coords(g["coordinates"], prec)
    return g


def as_point(geom):
    """Representative point for any geometry."""
    return geom if geom.geom_type == "Point" else geom.centroid


def load(name: str) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(GEO / f"{name}.geojson")
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        gdf = gdf.to_crs(epsg=4326)
    gdf = gdf.clip(THEATRE)
    return gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty]


def first(props: dict, *keys: str) -> str | None:
    for k in keys:
        v = props.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None


def dump(path: Path, features: list[dict], meta: dict) -> None:
    fc = {"type": "FeatureCollection", "metadata": meta, "features": features}
    path.write_text(json.dumps(fc, separators=(",", ":")), encoding="utf-8")
    print(f"  -> {path.relative_to(ROOT)}  {path.stat().st_size // 1024} KB · {len(features)} features")


def line_feature(geom, name, cat) -> dict:
    return {
        "type": "Feature",
        "geometry": geom_dict(geom),
        "properties": {"name": name, "cat": cat, "s": SCORES[cat]},
    }


# ---- 1 · jurisdiction --------------------------------------------------------
def build_jurisdiction() -> None:
    print("[jurisdiction]")
    feats: list[dict] = []
    for fname, zone, tol in (
        ("marine_regions_eez_baltic", "eez", 0.03),
        ("marine_regions_12nm", "territorial", 0.018),
    ):
        path = GEO / f"{fname}.geojson"
        if not path.exists():
            print(f"  !! missing {path.name} — run sync_from_s3 / WFS fetch first", file=sys.stderr)
            continue
        gdf = gpd.read_file(path)
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        gdf = gdf.clip(THEATRE)
        for _, row in gdf.iterrows():
            if row.geometry is None or row.geometry.is_empty:
                continue
            terr = first(row.drop(labels="geometry").dropna().astype(str).to_dict(),
                         "territory1", "TERRITORY1", "geoname", "GEONAME") or "?"
            geom = row.geometry
            if geom.geom_type == "GeometryCollection":  # clip artifact: keep polygonal parts
                from shapely.ops import unary_union
                polys = [g for g in geom.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
                if not polys:
                    continue
                geom = unary_union(polys)
            boundary = geom.boundary
            if boundary is None:
                continue
            # Archipelago territories produce thousands of tiny island rings —
            # keep only substantial boundary parts (the seaward lines).
            if boundary.geom_type == "MultiLineString":
                from shapely.geometry import MultiLineString
                parts = [p for p in boundary.geoms if p.length > 0.15]
                if not parts:
                    continue
                boundary = MultiLineString(parts)
            boundary = boundary.simplify(tol)
            if boundary.is_empty:
                continue
            feats.append({
                "type": "Feature",
                "geometry": geom_dict(boundary, prec=3),
                "properties": {"zone": zone, "territory": terr},
            })
    dump(OUT / "jurisdiction.json", feats, {
        "source": "Marine Regions (VLIZ), Maritime Boundaries — EEZ v12 + Territorial Seas 12NM",
        "license": "CC-BY 4.0",
        "zones": {"eez": "Exclusive Economic Zone boundary", "territorial": "12nm territorial sea (eaux territoriales)"},
    })


# ---- 2 · infrastructure lines -------------------------------------------------
def build_lines() -> None:
    print("[infra lines]")
    feats: list[dict] = []

    cables = load("submarine_cables")
    cables = cables[cables.geometry.length > 0.03]  # drop harbor stubs
    for _, r in cables.iterrows():
        feats.append(line_feature(r.geometry.simplify(0.005),
                                  first(r.to_dict(), "name") or "submarine cable", "telecom_cable"))

    power = load("submarine_power_cables")
    for _, r in power.iterrows():
        feats.append(line_feature(r.geometry.simplify(0.005),
                                  first(r.to_dict(), "name") or "power cable", "power_cable"))

    pipes = load("emodnet_pipelines")
    for _, r in pipes.iterrows():
        feats.append(line_feature(r.geometry.simplify(0.005),
                                  first(r.to_dict(), "name") or "pipeline", "pipeline"))

    dump(OUT / "infra_lines.json", feats, {
        "source": "OSM (ODbL) + EMODnet Human Activities (CC-BY 4.0)",
        "categories": {k: SCORES[k] for k in ("telecom_cable", "power_cable", "pipeline")},
    })


# ---- 3 · points of interest ---------------------------------------------------
def poi(lon, lat, name, cat) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [round(lon, PREC), round(lat, PREC)]},
        "properties": {"name": name, "cat": cat, "s": SCORES[cat]},
    }


def build_poi() -> None:
    print("[poi]")
    feats: list[dict] = []

    for _, r in load("naval_bases").iterrows():
        g = as_point(r.geometry)
        feats.append(poi(g.x, g.y, first(r.to_dict(), "name:en", "name") or "naval base", "naval_base"))

    for _, r in load("chokepoints").iterrows():
        g = as_point(r.geometry)
        feats.append(poi(g.x, g.y, first(r.to_dict(), "name") or "chokepoint", "chokepoint"))

    ports = load("ports")
    ports = ports[ports["leisure"].isna()] if "leisure" in ports.columns else ports
    named = ports[ports.apply(lambda r: bool(first(r.to_dict(), "name", "seamark:name")), axis=1)]
    for _, r in named.iterrows():
        g = as_point(r.geometry)
        feats.append(poi(g.x, g.y, first(r.to_dict(), "name", "seamark:name"), "port"))

    refi = load("refineries_lng")
    for _, r in refi.iterrows():
        c = r.geometry.centroid
        name = first(r.to_dict(), "name", "operator") or "energy terminal"
        feats.append(poi(c.x, c.y, name, "energy_terminal"))

    for _, r in load("emodnet_windfarms_point").iterrows():
        g = as_point(r.geometry)
        feats.append(poi(g.x, g.y, first(r.to_dict(), "name") or "wind farm", "windfarm"))
    wind = load("offshore_wind")
    for _, r in wind.iterrows():
        c = r.geometry.centroid
        feats.append(poi(c.x, c.y, first(r.to_dict(), "name") or "wind farm", "windfarm"))

    for _, r in load("offshore_platforms").iterrows():
        g = as_point(r.geometry)
        feats.append(poi(g.x, g.y, first(r.to_dict(), "name") or "platform", "platform"))

    for _, r in load("osm_anchorages").iterrows():
        g = r.geometry.centroid
        feats.append(poi(g.x, g.y, first(r.to_dict(), "name", "description") or "anchorage", "anchorage"))

    lh = load("osm_lighthouses")
    def lh_range(r):
        try:
            return float(str(r.get("seamark:light:range", "")).split(";")[0])
        except (ValueError, TypeError):
            return 0.0
    lh = lh[lh.apply(lambda r: lh_range(r) >= 12 or bool(first(r.to_dict(), "name")), axis=1)]
    for _, r in lh.iterrows():
        g = as_point(r.geometry)
        feats.append(poi(g.x, g.y, first(r.to_dict(), "name") or "light", "lighthouse"))

    dump(OUT / "poi.json", feats, {
        "source": "OSM (ODbL), EMODnet (CC-BY 4.0), hand-curated chokepoints",
        "scoring": "v1 class-based strategic score `s` (0-1) — weights in scripts/geo/build_web_layers.py",
        "categories": {k: v for k, v in SCORES.items()},
    })


if __name__ == "__main__":
    build_jurisdiction()
    build_lines()
    build_poi()
    print("done.")
