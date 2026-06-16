"""Download all Sentinel-1 SAR GeoTIFF scenes for any incident in incidents.csv.

Queries the Copernicus Sentinel Hub Catalog API for every S1-GRD acquisition
within ±WINDOW_DAYS of the incident date, downloads each scene as a 2-band
float32 GeoTIFF (VV + VH), and uploads to S3.

Outputs:
  data/sar/sentinel1/geotiff/<incident_id>_<scene_date>_<orbit>.tif
  + s3://edth2026-baltic/sar/sentinel1/geotiff/<filename>

Usage:
  python scripts/ingest/fetch_incident_sentinel1_geotiff.py INC-2024-11-18
  python scripts/ingest/fetch_incident_sentinel1_geotiff.py --list
  python scripts/ingest/fetch_incident_sentinel1_geotiff.py INC-2024-11-18 --window 7

Auth: COPERNICUS_CLIENT_ID + COPERNICUS_CLIENT_SECRET from .env.local
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env.local")

CLIENT_ID     = os.environ.get("COPERNICUS_CLIENT_ID")
CLIENT_SECRET = os.environ.get("COPERNICUS_CLIENT_SECRET")

TOKEN_URL   = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CATALOG_URL = "https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"

DEST_BUCKET = "edth2026-baltic"
DEST_PREFIX = "sar/sentinel1/geotiff"
HALF_DEG    = 0.15   # ~16 km halfwidth
OUT_DIR     = ROOT / "data" / "sar" / "sentinel1" / "geotiff"

EVALSCRIPT = """
//VERSION=3
function setup() {
  return { input: ["VV", "VH"], output: { bands: 2, sampleType: "FLOAT32" } };
}
function evaluatePixel(s) { return [s.VV, s.VH]; }
"""


# ── Incidents ─────────────────────────────────────────────────────────────────

def load_incidents() -> dict[str, dict]:
    incidents = {}
    with open(ROOT / "data" / "reference" / "incidents.csv") as f:
        for row in csv.DictReader(f):
            incidents[row["incident_id"]] = row
    return incidents


# ── Auth ──────────────────────────────────────────────────────────────────────

def get_token() -> str:
    r = requests.post(
        TOKEN_URL,
        data={"grant_type": "client_credentials",
              "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


# ── Catalog ───────────────────────────────────────────────────────────────────

def list_scenes(token: str, lat: float, lon: float,
                date_from: str, date_to: str) -> list[dict]:
    bbox = [lon - HALF_DEG, lat - HALF_DEG, lon + HALF_DEG, lat + HALF_DEG]
    items, next_token = [], None
    while True:
        body: dict = {
            "bbox": bbox,
            "datetime": f"{date_from}/{date_to}",
            "collections": ["sentinel-1-grd"],
            "limit": 100,
        }
        if next_token:
            body["next"] = next_token
        r = requests.post(
            CATALOG_URL, json=body,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/json"},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        items.extend(data.get("features", []))
        next_token = data.get("context", {}).get("next")
        if not next_token:
            break
    return items


# ── Download ──────────────────────────────────────────────────────────────────

def download_scene(token: str, lat: float, lon: float,
                   scene_dt: datetime, orbit_dir: str) -> bytes | None:
    date_from = (scene_dt - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    date_to   = (scene_dt + timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    bbox = [lon - HALF_DEG, lat - HALF_DEG, lon + HALF_DEG, lat + HALF_DEG]
    body = {
        "input": {
            "bounds": {"bbox": bbox,
                       "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"}},
            "data": [{"type": "sentinel-1-grd", "dataFilter": {
                "timeRange": {"from": date_from, "to": date_to},
                "mosaickingOrder": "mostRecent",
                "orbitDirection": orbit_dir,
            }}],
        },
        "output": {
            "width": 2048, "height": 2048,
            "responses": [{"identifier": "default",
                           "format": {"type": "image/tiff",
                                      "parameters": {"dataType": "float32"}}}],
        },
        "evalscript": EVALSCRIPT,
    }
    r = requests.post(PROCESS_URL, json=body,
                      headers={"Authorization": f"Bearer {token}", "Accept": "image/tiff"},
                      timeout=180)
    if r.status_code != 200:
        print(f"    HTTP {r.status_code}: {r.text[:200]}", flush=True)
        return None
    return r.content


# ── Main ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("incident_id", nargs="?", help="e.g. INC-2024-11-18")
    p.add_argument("--window", type=int, default=14, help="Days ± around incident date")
    p.add_argument("--list", action="store_true", help="List available incidents and exit")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    incidents = load_incidents()

    if args.list:
        print(f"{'ID':22s}  {'date':12s}  {'lat':>6}  {'lon':>6}  name")
        for inc_id, row in incidents.items():
            print(f"{inc_id:22s}  {row['date_utc']:12s}  "
                  f"{float(row['lat_approx']):6.1f}  {float(row['lon_approx']):6.1f}  "
                  f"{row['name'][:50]}")
        return 0

    if not args.incident_id:
        print("ERROR: provide an incident_id or --list", file=sys.stderr)
        return 1

    if args.incident_id not in incidents:
        print(f"ERROR: {args.incident_id} not in incidents.csv — use --list", file=sys.stderr)
        return 1

    if not (CLIENT_ID and CLIENT_SECRET):
        print("ERROR: COPERNICUS_CLIENT_ID / SECRET missing in .env.local", file=sys.stderr)
        return 1

    inc      = incidents[args.incident_id]
    inc_id   = args.incident_id
    lat      = float(inc["lat_approx"])
    lon      = float(inc["lon_approx"])
    inc_date = datetime.fromisoformat(inc["date_utc"]).replace(tzinfo=timezone.utc)
    date_from = (inc_date - timedelta(days=args.window)).strftime("%Y-%m-%dT00:00:00Z")
    date_to   = (inc_date + timedelta(days=args.window)).strftime("%Y-%m-%dT23:59:59Z")

    print(f"Incident : {inc_id} — {inc['name']}")
    print(f"Location : {lat}°N {lon}°E")
    print(f"Window   : {date_from[:10]} → {date_to[:10]}", flush=True)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    s3 = boto3.Session(profile_name="edth2026").client("s3", region_name="eu-west-3")

    print("Authenticating...", flush=True)
    token = get_token()

    print("Querying catalog...", flush=True)
    scenes = list_scenes(token, lat, lon, date_from, date_to)
    print(f"  Found {len(scenes)} S1-GRD scenes", flush=True)

    if not scenes:
        print("No scenes found — check credentials or widen --window.")
        return 1

    downloaded = 0
    for item in scenes:
        props     = item.get("properties", {})
        dt_str    = props.get("datetime", "")
        orbit_dir = props.get("sat:orbit_state", "unknown").upper()
        try:
            scene_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            continue

        scene_label = scene_dt.strftime("%Y-%m-%dT%H%M%S")
        filename    = f"{inc_id}_{scene_label}_{orbit_dir}.tif"
        out_path    = OUT_DIR / filename
        s3_key      = f"{DEST_PREFIX}/{filename}"

        print(f"\n  {scene_label} ({orbit_dir})", flush=True)
        if out_path.exists():
            print("    cache hit")
        else:
            tif = download_scene(token, lat, lon, scene_dt, orbit_dir)
            if not tif or len(tif) < 1000:
                print("    no data returned")
                continue
            out_path.write_bytes(tif)
            print(f"    saved {len(tif)//1024} KB → {out_path.name}")
            downloaded += 1

        print(f"    uploading to s3://{DEST_BUCKET}/{s3_key}", flush=True)
        s3.upload_file(str(out_path), DEST_BUCKET, s3_key)

    print(f"\nDone — {downloaded} new scenes downloaded.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
