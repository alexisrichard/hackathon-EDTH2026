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
    "power_plant":   0.75,  # thermal; nuclear overridden to 0.90 per-feature
    "naval_base":    0.85,
    "converter":     0.85,  # HVDC converter stations — subsea power-cable landings
    "energy_terminal": 0.80,
    "restricted_zone": 0.70,  # military / danger / exercise areas
    "port":          0.65,
    "windfarm":      0.60,
    "platform":      0.60,
    "anchorage":     0.40,
    "shipping_lane": 0.25,  # context line, not a target (score unused for rendering)
    # lighthouses dropped — navigation aids, not strategic targets
}

# Working harbours only — OSM tags ~2,200 recreational marinas as "ports".
COMMERCIAL_PORTS = {"cargo", "container", "bulk", "passenger", "ferry", "naval", "fishing"}

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


# Coastal band — drops far-inland clutter (Belarus oil fields, Scandinavian
# micro-hydro) while keeping anything maritime-relevant. ~0.55° ≈ 40–60 km.
_COAST_BAND = None


def near_coast(geom) -> bool:
    global _COAST_BAND
    if _COAST_BAND is None:
        from shapely.ops import unary_union
        from shapely.prepared import prep
        cl = gpd.read_file(GEO / "ne_coastline_10m.geojson")
        if cl.crs and cl.crs.to_epsg() != 4326:
            cl = cl.to_crs(epsg=4326)
        _COAST_BAND = prep(unary_union(list(cl.geometry)).buffer(0.55))
    return _COAST_BAND.contains(as_point(geom))


# Tight (~8 km) coastline band — a subsea cable "lands" here. Used to drop
# OSM cable fragments that dead-end in open water (incomplete traces).
_LANDING_BAND = None


def lands_on_coast(geom) -> bool:
    """True if BOTH endpoints of a (Multi)LineString are near a coast (coast-to-coast)."""
    global _LANDING_BAND
    if _LANDING_BAND is None:
        from shapely.ops import unary_union
        from shapely.prepared import prep
        cl = gpd.read_file(GEO / "ne_coastline_10m.geojson")
        if cl.crs and cl.crs.to_epsg() != 4326:
            cl = cl.to_crs(epsg=4326)
        _LANDING_BAND = prep(unary_union(list(cl.geometry)).buffer(0.08))
    from shapely.geometry import Point
    if geom.geom_type == "MultiLineString":
        cs = [p for ln in geom.geoms for p in ln.coords]
    else:
        cs = list(geom.coords)
    if len(cs) < 2:
        return False
    return _LANDING_BAND.contains(Point(cs[0])) and _LANDING_BAND.contains(Point(cs[-1]))


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


# ISO-3 codes for marine-zone territories (labels along boundary lines)
TERRITORY_CODES = {
    "Denmark": "DNK", "Sweden": "SWE", "Finland": "FIN", "Estonia": "EST",
    "Latvia": "LVA", "Lithuania": "LTU", "Poland": "POL", "Germany": "DEU",
    "Russia": "RUS", "Norway": "NOR", "United Kingdom": "GBR", "Netherlands": "NLD",
    "Belgium": "BEL", "France": "FRA", "Alaska": "USA", "Kaliningrad": "RUS",
}


# ---- 1 · jurisdiction --------------------------------------------------------
def build_jurisdiction() -> None:
    print("[jurisdiction]")
    feats: list[dict] = []

    # Country land borders (incl. coastlines) — Natural Earth, zone='border'
    ne = load("ne_countries_50m")
    for _, row in ne.iterrows():
        name = str(row.get("NAME", "?"))
        code = str(row.get("ISO_A3", "") or row.get("ADM0_A3", ""))[:3]
        boundary = row.geometry.boundary
        if boundary is None or boundary.is_empty:
            continue
        boundary = boundary.simplify(0.02)
        feats.append({
            "type": "Feature",
            "geometry": geom_dict(boundary, prec=3),
            "properties": {"zone": "border", "territory": name, "code": code},
        })
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
                "properties": {"zone": zone, "territory": terr,
                               "code": TERRITORY_CODES.get(terr, terr[:3].upper())},
            })
    dump(OUT / "jurisdiction.json", feats, {
        "source": "Marine Regions (VLIZ) EEZ v12 + Territorial Seas 12NM (CC-BY 4.0); Natural Earth countries (CC0)",
        "zones": {"border": "country boundary", "eez": "Exclusive Economic Zone boundary",
                  "territorial": "12nm territorial sea (eaux territoriales)"},
        "todo": "rescue/SRR zones — no open layer found on Marine Regions WFS; revisit (IMO SRR sources)",
    })


# ---- 2 · infrastructure lines -------------------------------------------------
def build_lines() -> None:
    print("[infra lines]")
    feats: list[dict] = []

    # Coast-to-coast only: subsea cables must land on two shores. Drops OSM
    # fragments that dead-end in open water (incomplete traces).
    cables = load("submarine_cables")
    cables = cables[cables.geometry.length > 0.03]  # drop harbor stubs
    kept = dropped = 0
    for _, r in cables.iterrows():
        if not lands_on_coast(r.geometry):
            dropped += 1
            continue
        kept += 1
        feats.append(line_feature(r.geometry.simplify(0.005),
                                  first(r.to_dict(), "name") or "submarine cable", "telecom_cable"))
    print(f"    telecom cables: kept {kept} coast-to-coast, dropped {dropped} dead-ending", flush=True)

    power = load("submarine_power_cables")
    for _, r in power.iterrows():
        if not lands_on_coast(r.geometry):
            continue
        feats.append(line_feature(r.geometry.simplify(0.005),
                                  first(r.to_dict(), "name") or "power cable", "power_cable"))

    pipes = load("emodnet_pipelines")
    for _, r in pipes.iterrows():
        feats.append(line_feature(r.geometry.simplify(0.005),
                                  first(r.to_dict(), "name") or "pipeline", "pipeline"))

    # Shipping lanes — IMO traffic separation schemes (lane/boundary/line).
    tss = load("osm_tss")
    tss = tss[tss.geometry.geom_type == "LineString"]
    for _, r in tss.iterrows():
        label = str(r.get("seamark:type") or "").replace("separation_", "").replace("_", " ") or "shipping lane"
        feats.append(line_feature(r.geometry.simplify(0.003), label, "shipping_lane"))

    dump(OUT / "infra_lines.json", feats, {
        "source": "OSM (ODbL) + EMODnet Human Activities (CC-BY 4.0)",
        "categories": {k: SCORES[k] for k in ("telecom_cable", "power_cable", "pipeline", "shipping_lane")},
    })


# ---- 3 · points of interest ---------------------------------------------------
def poi(lon, lat, name, cat) -> dict:
    return {
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [round(lon, PREC), round(lat, PREC)]},
        "properties": {"name": name, "cat": cat, "s": SCORES[cat]},
    }


# Cluster radius per category, in degrees latitude (~111 km/deg). OSM industrial
# complexes arrive as dozens of unnamed polygon fragments — merge same-category
# points within radius into ONE site, named after the best-named member.
CLUSTER_RADIUS = {
    "energy_terminal": 0.040,  # ~4.5 km — refinery/terminal complexes
    "windfarm": 0.060,         # ~7 km — also dedupes EMODnet vs OSM
    "anchorage": 0.045,        # ~5 km — harbour approaches stack up
    "platform": 0.020,
    "port": 0.022,             # ~2.4 km — merge multi-node harbour complexes
    "lighthouse": 0.055,       # ~6 km — coastal navigation-aid chains (the big one)
}
GENERIC_NAMES = {"energy terminal", "wind farm", "anchorage", "platform", "port", "naval base", "light"}
LON_SCALE = 0.53  # cos(58°) — equirect distance correction for the theatre


def cluster_category(feats: list[dict], radius: float) -> list[dict]:
    """Greedy centroid clustering of same-category point features."""
    clusters: list[dict] = []
    for f in feats:
        x, y = f["geometry"]["coordinates"]
        name = f["properties"]["name"]
        hit = None
        for c in clusters:
            dx = (c["x"] - x) * LON_SCALE
            dy = c["y"] - y
            if dx * dx + dy * dy < radius * radius:
                hit = c
                break
        if hit is None:
            clusters.append({"x": x, "y": y, "n": 1, "names": [name], "cat": f["properties"]["cat"]})
        else:
            hit["n"] += 1
            hit["x"] += (x - hit["x"]) / hit["n"]  # running centroid
            hit["y"] += (y - hit["y"]) / hit["n"]
            hit["names"].append(name)
    out = []
    for c in clusters:
        real = [n for n in c["names"] if n and n.lower() not in GENERIC_NAMES]
        best = max(real, key=len) if real else c["names"][0]
        p = poi(c["x"], c["y"], best, c["cat"])
        p["properties"]["n"] = c["n"]
        out.append(p)
    return out


def cluster_all(feats: list[dict]) -> list[dict]:
    by_cat: dict[str, list[dict]] = {}
    for f in feats:
        by_cat.setdefault(f["properties"]["cat"], []).append(f)
    out: list[dict] = []
    for cat, items in by_cat.items():
        if cat in CLUSTER_RADIUS:
            merged = cluster_category(items, CLUSTER_RADIUS[cat])
            print(f"    {cat}: {len(items)} -> {len(merged)} sites")
            out.extend(merged)
        else:
            for f in items:
                f["properties"]["n"] = 1
            out.extend(items)
    return out


def build_poi() -> None:
    print("[poi]")
    feats: list[dict] = []

    for _, r in load("naval_bases").iterrows():
        g = as_point(r.geometry)
        feats.append(poi(g.x, g.y, first(r.to_dict(), "name:en", "name") or "naval base", "naval_base"))

    ports = load("ports")
    for _, r in ports.iterrows():
        cat = str(r.get("seamark:harbour:category") or "")
        if cat not in COMMERCIAL_PORTS:  # skip the ~2,200 recreational marinas
            continue
        g = as_point(r.geometry)
        feats.append(poi(g.x, g.y, first(r.to_dict(), "name", "seamark:name") or f"{cat} harbour", "port"))

    refi = load("refineries_lng")
    for _, r in refi.iterrows():
        if not near_coast(r.geometry):  # drops inland Belarus oil-field gathering stations
            continue
        c = r.geometry.centroid
        name = first(r.to_dict(), "name", "operator") or "energy terminal"
        feats.append(poi(c.x, c.y, name, "energy_terminal"))

    # power plants — strategic carriers only; nuclear scored highest + always kept
    STRAT_SRC = ("nuclear", "gas", "coal", "oil", "diesel", "combined")
    for _, r in load("power_plants").iterrows():
        src = str(r.get("plant:source") or "").lower()
        nuclear = "nuclear" in src or str(r.get("plant:method")) == "fission"
        if not nuclear and not any(s in src for s in STRAT_SRC):
            continue  # drop hydro / biomass / biogas / solar
        if not nuclear and not near_coast(r.geometry):
            continue  # keep all nuclear; coastal-clip thermal
        g = as_point(r.geometry)
        name = first(r.to_dict(), "name") or (f"{src.split(';')[0]} power plant" if src else "power plant")
        f = poi(g.x, g.y, name, "power_plant")
        f["properties"]["kind"] = "nuclear" if nuclear else (src.split(";")[0] or "thermal")
        if nuclear:
            f["properties"]["s"] = 0.90
        feats.append(f)

    # HVDC converter stations — subsea power-cable landings (substation=converter
    # only; the bare power=converter tag is full of pipeline cathodic-protection units)
    for _, r in load("converter_stations").iterrows():
        if str(r.get("substation")) != "converter":
            continue
        if not near_coast(r.geometry):  # keep subsea-cable landings, drop inland AC/DC substations
            continue
        g = as_point(r.geometry)
        feats.append(poi(g.x, g.y, first(r.to_dict(), "name") or "HVDC converter", "converter"))

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

    feats = cluster_all(feats)
    dump(OUT / "poi.json", feats, {
        "source": "OSM (ODbL), EMODnet (CC-BY 4.0), hand-curated chokepoints",
        "scoring": "v1 class-based strategic score `s` (0-1) — weights in scripts/geo/build_web_layers.py",
        "clustering": "same-category sites merged within CLUSTER_RADIUS; `n` = member count, name = best-named member",
        "categories": {k: v for k, v in SCORES.items()},
    })


# ---- 4 · restricted / military zones (polygons) -------------------------------
# OSM tags 1,277 "restricted areas" but most are bird sanctuaries / nature
# reserves / swimming areas. Keep only the defense-relevant ones.
ZONE_CATEGORIES = {"military", "safety"}  # seamark:restricted_area:category


def build_zones() -> None:
    print("[zones]")
    g = load("osm_restricted_areas")
    feats: list[dict] = []
    def clean(v) -> str:  # geopandas missing values are NaN floats -> "nan"
        s = str(v).strip()
        return "" if s.lower() in ("nan", "none", "") else s

    for _, r in g.iterrows():
        p = r.to_dict()
        cat = clean(p.get("seamark:restricted_area:category"))
        mil = clean(p.get("military"))  # training_area / danger_area / range
        if cat not in ZONE_CATEGORIES and not mil:
            continue
        geom = r.geometry
        if geom is None or geom.is_empty:
            continue
        geom = geom.simplify(0.004)
        kind = mil.replace("_", " ") if mil else cat
        name = first(p, "name", "seamark:name") or f"{kind} zone"
        feats.append({
            "type": "Feature",
            "geometry": geom_dict(geom, prec=4),
            "properties": {"cat": "restricted_zone", "name": name, "kind": kind, "s": SCORES["restricted_zone"]},
        })
    dump(OUT / "zones.json", feats, {
        "source": "OSM seamark restricted_area (ODbL), filtered to military/danger/safety",
        "note": "excludes bird sanctuaries, nature reserves, swimming areas (not defense-relevant)",
        "score": SCORES["restricted_zone"],
    })


# ---- 5 · fishing intensity (heatmap input) -----------------------------------
# HELCOM AIS-derived fishing effort. `fhr` = fishing hours per 0.05° cell.
# Lets an operator spot a "fishing" vessel working where nobody actually fishes
# — the fake-trawler tell. Coverage: SW Baltic / Kattegat–Bornholm (2020 Q1).
def build_fishing() -> None:
    print("[fishing]")
    g = load("helcom_fishing_intensity_total_2016_2021")
    feats: list[dict] = []
    for _, r in g.iterrows():
        fhr = r.get("fhr")
        if not isinstance(fhr, (int, float)) or fhr <= 0:
            continue
        lon, lat = r.get("lon"), r.get("lat")
        if not isinstance(lon, (int, float)) or not isinstance(lat, (int, float)):
            c = r.geometry.centroid
            lon, lat = c.x, c.y
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [round(float(lon), 3), round(float(lat), 3)]},
            "properties": {"fhr": round(float(fhr), 1)},
        })
    dump(OUT / "fishing_intensity.json", feats, {
        "source": "HELCOM AIS-derived fishing intensity, gear total, 2020 Q1",
        "field": "fhr = fishing hours per ~0.05° cell",
        "coverage": "SW Baltic / Kattegat–Bornholm (HELCOM extent)",
        "note": "zero-effort cells dropped",
    })


if __name__ == "__main__":
    build_jurisdiction()
    build_lines()
    build_poi()
    build_zones()
    build_fishing()
    print("done.")
