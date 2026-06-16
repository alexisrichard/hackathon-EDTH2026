"""Build the two 'Incidents - dev' web layers:

  frontend/public/data/incidents.json     9 incident points (data/reference/incidents.csv),
                                           each tagged with measured AIS coverage at its zone/date
  frontend/public/data/ais_coverage.json  data-derived reliable/marginal AIS coverage zone

The coverage zone is NOT hand-drawn: it is the dissolved set of 0.25 deg grid cells
binned from real Danish-AIS day-files, classified by how many distinct vessels we
actually receive there (over a sample of incident days). This is the honest answer
to "where do we have reliable AIS" — dense in the western Baltic, gone east of Gotland.

AIS day-files are read from /tmp/ais_incidents/<incident_id>.parquet (one Danish-AIS
day per incident, pre-downloaded). If absent, incident points are still built from the
CSV (coverage metrics null) and the coverage zone is skipped.

Run:  python scripts/geo/build_incidents_dev_layers.py
"""
import csv, glob, json, math
from pathlib import Path

import duckdb
from shapely.geometry import box, mapping
from shapely.ops import unary_union

REPO = Path(__file__).resolve().parents[2]
CSV = REPO / "data" / "reference" / "incidents.csv"
OUT = REPO / "frontend" / "public" / "data"
AIS_DIR = Path("/tmp/ais_incidents")

# Baltic grid for the coverage zone
CELL = 0.25
BBOX = (9, 53, 30, 66)  # lon0, lat0, lon1, lat1
RELIABLE_MIN = 30       # distinct vessels (over the sample days) for "reliable"
MARGINAL_MIN = 5        # ... for "marginal" (fringe reception)

# incident coverage verdict from vessels within 80 km of the damage point that day
def verdict(vessels_80km: int | None) -> str:
    if vessels_80km is None:
        return "unknown"
    if vessels_80km >= 50:
        return "reliable"
    if vessels_80km >= 10:
        return "marginal"
    return "gap"

SHORT = {
    "INC-2022-09-26": "Nord Stream", "INC-2023-10-08": "Balticconnector",
    "INC-2024-11-17": "BCS E-W", "INC-2024-11-18": "C-Lion1",
    "INC-2024-12-25": "Eagle S", "INC-2025-01-26": "Vezhen",
    "INC-2025-02-21": "Cinia", "INC-2025-12-31": "Fitburg",
    "INC-2026-01-02": "Sventoji-Liepaja",
}

con = duckdb.connect()


def incident_metrics(iid: str, lat: float, lon: float):
    """Measured AIS coverage around (lat,lon) on the incident's own day-file."""
    pq = AIS_DIR / f"{iid}.parquet"
    if not pq.exists():
        return None
    hav = (f"6371*2*asin(sqrt(power(sin(radians(Latitude-{lat})/2),2)"
           f"+cos(radians({lat}))*cos(radians(Latitude))"
           f"*power(sin(radians(Longitude-{lon})/2),2)))")
    box80 = (f"Latitude BETWEEN {lat-0.75} AND {lat+0.75} "
             f"AND Longitude BETWEEN {lon-1.35} AND {lon+1.35}")
    row = con.execute(f"""
        SELECT COUNT(*) FILTER (WHERE {box80}),
               COUNT(DISTINCT MMSI) FILTER (WHERE {box80}),
               MIN({hav})
        FROM read_parquet('{pq}')
    """).fetchone()
    msgs80, vessels80, nearest = row
    return {"msgs_80km": int(msgs80), "vessels_80km": int(vessels80),
            "nearest_km": round(nearest, 1) if nearest is not None else None}


def build_incidents():
    feats = []
    for i, r in enumerate(csv.DictReader(CSV.open()), start=1):
        iid = r["incident_id"]
        lat, lon = float(r["lat_approx"]), float(r["lon_approx"])
        m = incident_metrics(iid, lat, lon) or {}
        v = verdict(m.get("vessels_80km"))
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "id": iid, "n": i, "short": SHORT.get(iid, iid),
                "name": r["name"], "date": r["date_utc"], "time_utc": r["time_utc"],
                "vessel": r["vessel_name"], "flag": r["vessel_flag"],
                "infra": r["infrastructure_name"], "infra_type": r["infrastructure_type"],
                "status": r["attribution_status"], "region": r["region"],
                "coverage": v, **m,
            },
        })
    fc = {"type": "FeatureCollection", "features": feats}
    (OUT / "incidents.json").write_text(json.dumps(fc))
    counts = {"reliable": 0, "marginal": 0, "gap": 0, "unknown": 0}
    for f in feats:
        counts[f["properties"]["coverage"]] += 1
    print(f"incidents.json: {len(feats)} points  {counts}")


def build_coverage():
    files = sorted(glob.glob(str(AIS_DIR / "*.parquet")))
    if not files:
        print("ais_coverage.json: SKIPPED (no day-files in /tmp/ais_incidents)")
        return
    lo0, la0, lo1, la1 = BBOX
    parts = [
        f"SELECT DISTINCT MMSI, floor(Latitude/{CELL})*{CELL} la, floor(Longitude/{CELL})*{CELL} lo "
        f"FROM read_parquet('{f}') WHERE Latitude BETWEEN {la0} AND {la1} AND Longitude BETWEEN {lo0} AND {lo1}"
        for f in files
    ]
    cells = con.execute(
        "SELECT la, lo, COUNT(DISTINCT MMSI) nv FROM ("
        + " UNION ALL ".join(parts) + ") GROUP BY la, lo"
    ).fetchall()

    tiers = {"reliable": [], "marginal": []}
    for la, lo, nv in cells:
        cell = box(lo, la, lo + CELL, la + CELL)
        if nv >= RELIABLE_MIN:
            tiers["reliable"].append(cell)
        elif nv >= MARGINAL_MIN:
            tiers["marginal"].append(cell)

    feats = []
    for tier, boxes in tiers.items():
        if not boxes:
            continue
        geom = unary_union(boxes)
        feats.append({
            "type": "Feature",
            "geometry": mapping(geom),
            "properties": {
                "tier": tier, "n_days": len(files),
                "min_vessels": RELIABLE_MIN if tier == "reliable" else MARGINAL_MIN,
                "cell_deg": CELL,
            },
        })
    fc = {"type": "FeatureCollection", "features": feats}
    (OUT / "ais_coverage.json").write_text(json.dumps(fc))
    sizes = {t: len(b) for t, b in tiers.items()}
    print(f"ais_coverage.json: {len(feats)} tiers from {len(files)} days  cells={sizes}")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    build_incidents()
    build_coverage()
