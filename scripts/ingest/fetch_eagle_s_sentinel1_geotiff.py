"""Download all Sentinel-1 SAR GeoTIFF scenes covering the Eagle S incident.

Queries the Copernicus Sentinel Hub Catalog API for every S1-GRD acquisition
within ±14 days of 2024-12-25 over the Gulf of Finland (60.30°N 26.50°E),
then downloads each scene individually as a 2-band float32 GeoTIFF (VV + VH).

Outputs:
  data/sar/sentinel1/geotiff/INC-2024-12-25_<scene_date>_<orbit>.tif
  + uploaded to s3://edth2026-baltic/sar/sentinel1/geotiff/<filename>

Auth: COPERNICUS_CLIENT_ID + COPERNICUS_CLIENT_SECRET from .env.local
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env.local")

CLIENT_ID = os.environ.get("COPERNICUS_CLIENT_ID")
CLIENT_SECRET = os.environ.get("COPERNICUS_CLIENT_SECRET")
if not (CLIENT_ID and CLIENT_SECRET):
    print("ERROR: COPERNICUS_CLIENT_ID / SECRET missing in .env.local", file=sys.stderr)
    sys.exit(1)

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CATALOG_URL = "https://sh.dataspace.copernicus.eu/api/v1/catalog/1.0.0/search"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"

INCIDENT_ID = "INC-2024-12-25"
INCIDENT_DATE = datetime(2024, 12, 25, tzinfo=timezone.utc)
LAT = 60.30
LON = 26.50
HALF_DEG = 0.15  # ~16 km lat halfwidth; ~8 km lon at 60°N
WINDOW_DAYS = 14

OUT_DIR = ROOT / "data" / "sar" / "sentinel1" / "geotiff"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEST_BUCKET = "edth2026-baltic"
DEST_PREFIX = "sar/sentinel1/geotiff"

# 2-band float32 evalscript — raw linear backscatter (VV, VH)
EVALSCRIPT_S1_FLOAT = """
//VERSION=3
function setup() {
  return {
    input: ["VV", "VH"],
    output: { bands: 2, sampleType: "FLOAT32" }
  };
}
function evaluatePixel(s) {
  return [s.VV, s.VH];
}
"""


def get_token() -> str:
    r = requests.post(
        TOKEN_URL,
        data={"grant_type": "client_credentials", "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def list_scenes(token: str) -> list[dict]:
    """Return catalog items for all S1-GRD acquisitions in the time window."""
    bbox = [LON - HALF_DEG, LAT - HALF_DEG, LON + HALF_DEG, LAT + HALF_DEG]
    date_from = (INCIDENT_DATE - timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%dT00:00:00Z")
    date_to = (INCIDENT_DATE + timedelta(days=WINDOW_DAYS)).strftime("%Y-%m-%dT23:59:59Z")

    items: list[dict] = []
    next_token: str | None = None

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
            CATALOG_URL,
            json=body,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        items.extend(data.get("features", []))

        next_token = data.get("context", {}).get("next")
        if not next_token:
            break

    return items


def download_scene(token: str, scene_dt: datetime, orbit_dir: str) -> bytes | None:
    """Download a single S1-GRD scene as a float32 GeoTIFF."""
    # Tight ±6 h window to isolate this specific pass
    date_from = (scene_dt - timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    date_to = (scene_dt + timedelta(hours=6)).strftime("%Y-%m-%dT%H:%M:%SZ")
    bbox = [LON - HALF_DEG, LAT - HALF_DEG, LON + HALF_DEG, LAT + HALF_DEG]

    body = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
            },
            "data": [{
                "type": "sentinel-1-grd",
                "dataFilter": {
                    "timeRange": {"from": date_from, "to": date_to},
                    "mosaickingOrder": "mostRecent",
                    "orbitDirection": orbit_dir,
                },
            }],
        },
        "output": {
            "width": 2048,
            "height": 2048,
            "responses": [{"identifier": "default", "format": {
                "type": "image/tiff",
                "parameters": {"dataType": "float32"},
            }}],
        },
        "evalscript": EVALSCRIPT_S1_FLOAT,
    }

    r = requests.post(
        PROCESS_URL,
        json=body,
        headers={"Authorization": f"Bearer {token}", "Accept": "image/tiff"},
        timeout=180,
    )
    if r.status_code != 200:
        print(f"    HTTP {r.status_code}: {r.text[:300]}", flush=True)
        return None
    return r.content


def main() -> int:
    print("Authenticating...", flush=True)
    token = get_token()
    print("  OK", flush=True)

    print("Querying catalog...", flush=True)
    scenes = list_scenes(token)
    print(f"  Found {len(scenes)} S1-GRD scenes", flush=True)

    if not scenes:
        print("No scenes found — check credentials or time window.", file=sys.stderr)
        return 1

    s3 = boto3.client("s3", region_name="eu-west-3")

    for item in scenes:
        props = item.get("properties", {})
        dt_str = props.get("datetime", "")
        orbit_dir = props.get("sat:orbit_state", "unknown").upper()

        try:
            scene_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        except ValueError:
            print(f"  Skipping item with unparseable datetime: {dt_str}", flush=True)
            continue

        scene_label = scene_dt.strftime("%Y-%m-%dT%H%M%S")
        filename = f"{INCIDENT_ID}_{scene_label}_{orbit_dir}.tif"
        out_path = OUT_DIR / filename
        s3_key = f"{DEST_PREFIX}/{filename}"

        print(f"\n  Scene {scene_label} ({orbit_dir})", flush=True)

        if out_path.exists():
            print("    cache hit — skipping download", flush=True)
        else:
            tif = download_scene(token, scene_dt, orbit_dir)
            if not tif or len(tif) < 1000:
                print("    no data returned", flush=True)
                continue
            out_path.write_bytes(tif)
            print(f"    -> {out_path} ({len(tif) // 1024} KB)", flush=True)

        print(f"    uploading to s3://{DEST_BUCKET}/{s3_key}", flush=True)
        s3.upload_file(str(out_path), DEST_BUCKET, s3_key)
        print("    done", flush=True)

    print("\nAll scenes processed.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
