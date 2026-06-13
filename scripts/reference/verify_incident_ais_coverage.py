"""Verify Danish-AIS coverage for each incident's zone+date.

For every row in data/reference/incidents.csv, query the Danish AIS Parquet for
that calendar day and report, around the incident lat/lon:
  - whole-day message + distinct-vessel counts (is the day present at all?)
  - counts inside a ~28 km (0.25 deg) and ~80 km (0.75 deg lat) zone box
  - distance (km) of the closest AIS ping to the damage point that day

Reads day-files pre-downloaded to /tmp/ais_incidents/<incident_id>.parquet
(httpfs streaming of the full 200-340 MB day-files times out).
"""
import csv
from pathlib import Path
import duckdb

REPO = Path(__file__).resolve().parents[2]
INC = REPO / "data" / "reference" / "incidents.csv"
LOCAL = Path("/tmp/ais_incidents")

c = duckdb.connect()
rows = list(csv.DictReader(INC.open()))
print(f"{len(rows)} incidents\n")

for r in rows:
    iid = r["incident_id"]
    d = r["date_utc"]
    lat = float(r["lat_approx"]); lon = float(r["lon_approx"])
    pq = LOCAL / f"{iid}.parquet"
    if not pq.exists():
        print(f"=== {iid}  {d}  MISSING LOCAL FILE {pq}\n"); continue

    hav = (f"6371*2*asin(sqrt(power(sin(radians(Latitude-{lat})/2),2)"
           f"+cos(radians({lat}))*cos(radians(Latitude))"
           f"*power(sin(radians(Longitude-{lon})/2),2)))")
    box25 = f"(Latitude BETWEEN {lat-0.25} AND {lat+0.25} AND Longitude BETWEEN {lon-0.45} AND {lon+0.45})"
    box75 = f"(Latitude BETWEEN {lat-0.75} AND {lat+0.75} AND Longitude BETWEEN {lon-1.35} AND {lon+1.35})"

    q = f"""
    SELECT
      COUNT(*) AS day_msgs,
      COUNT(DISTINCT MMSI) AS day_vessels,
      MIN(Latitude), MAX(Latitude), MIN(Longitude), MAX(Longitude),
      COUNT(*) FILTER (WHERE {box25}) AS m28,
      COUNT(DISTINCT MMSI) FILTER (WHERE {box25}) AS v28,
      COUNT(*) FILTER (WHERE {box75}) AS m80,
      COUNT(DISTINCT MMSI) FILTER (WHERE {box75}) AS v80,
      MIN({hav}) AS nearest_km
    FROM read_parquet('{pq}')
    """
    (dm, dv, mnla, mxla, mnlo, mxlo, m28, v28, m80, v80, near) = c.execute(q).fetchone()
    print(f"=== {iid}  {d}  ({lat:.2f},{lon:.2f})  {r['region']}")
    print(f"    day total : {dm:>11,} msgs  {dv:>5,} vessels   "
          f"extent lat[{mnla:.1f},{mxla:.1f}] lon[{mnlo:.1f},{mxlo:.1f}]")
    print(f"    <=28 km   : {m28:>11,} msgs  {v28:>5,} vessels")
    print(f"    <=80 km   : {m80:>11,} msgs  {v80:>5,} vessels")
    print(f"    nearest AIS ping to damage point: {near:.1f} km" if near is not None
          else "    nearest ping: n/a")
    print(flush=True)
