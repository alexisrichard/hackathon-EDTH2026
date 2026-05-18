"""Download Sentinel-2 true-color + Sentinel-1 SAR crops for each incident via
the Copernicus Data Space Sentinel Hub Process API.

For each incident in data/reference/incidents.csv:
  - Renders a 2048x2048 true-color Sentinel-2 image of a ~30km bbox around the
    incident point. Picks the cloud-free best scene within ±14 days.
  - Renders a 2048x2048 Sentinel-1 SAR image (VV/VH dual-pol composite).

Outputs:
  data/optical/sentinel2/<incident_id>_truecolor.jpg   (~ 1-3 MB each)
  data/sar/sentinel1/<incident_id>_sar.jpg             (~ 1-3 MB each)
  + uploaded to s3://edth2026-baltic/{optical,sar}/<...>

Auth: COPERNICUS_CLIENT_ID + COPERNICUS_CLIENT_SECRET from .env.local
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import io

import boto3
import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env.local")

CLIENT_ID = os.environ.get("COPERNICUS_CLIENT_ID")
CLIENT_SECRET = os.environ.get("COPERNICUS_CLIENT_SECRET")
if not (CLIENT_ID and CLIENT_SECRET):
    print("ERROR: COPERNICUS_CLIENT_ID / SECRET missing in .env.local", file=sys.stderr)
    sys.exit(1)

TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"

INCIDENTS_CSV = Path("data/reference/incidents.csv")
OUT_OPTICAL = Path("data/optical/sentinel2")
OUT_SAR = Path("data/sar/sentinel1")
OUT_OPTICAL.mkdir(parents=True, exist_ok=True)
OUT_SAR.mkdir(parents=True, exist_ok=True)

DEST_BUCKET = "edth2026-baltic"
WINDOW_DAYS = 14
HALF_DEG = 0.15  # ~16 km lat halfwidth; ~8 km lon at 60°N

# True-color Sentinel-2 — simplest possible script. Mosaicking is set in the
# request body, not in setup(). Output 3 bands for JPEG (no alpha).
EVALSCRIPT_S2_TRUECOLOR = """
//VERSION=3
function setup() {
  return {
    input: ["B02", "B03", "B04"],
    output: { bands: 3, sampleType: "AUTO" }
  };
}
function evaluatePixel(s) {
  return [2.5 * s.B04, 2.5 * s.B03, 2.5 * s.B02];
}
"""

# Sentinel-1 SAR dual-pol composite. Detects VV/VH (IW mode) vs HH/HV (EW mode).
EVALSCRIPT_S1_SAR = """
//VERSION=3
function setup() {
  return {
    input: ["VV", "VH"],
    output: { bands: 3, sampleType: "AUTO" }
  };
}
function evaluatePixel(s) {
  const vv = 10 * Math.log10(Math.max(s.VV, 1e-5));
  const vh = 10 * Math.log10(Math.max(s.VH, 1e-5));
  const r = Math.max(0, Math.min(1, (vv + 25) / 25));
  const g = Math.max(0, Math.min(1, (vh + 30) / 30));
  return [r, g, (r + g) / 2];
}
"""

# Sentinel-1 fallback for EW mode (HH/HV polarization)
EVALSCRIPT_S1_SAR_HH = """
//VERSION=3
function setup() {
  return {
    input: ["HH", "HV"],
    output: { bands: 3, sampleType: "AUTO" }
  };
}
function evaluatePixel(s) {
  const hh = 10 * Math.log10(Math.max(s.HH, 1e-5));
  const hv = 10 * Math.log10(Math.max(s.HV, 1e-5));
  const r = Math.max(0, Math.min(1, (hh + 25) / 25));
  const g = Math.max(0, Math.min(1, (hv + 30) / 30));
  return [r, g, (r + g) / 2];
}
"""


def is_blank(img_bytes: bytes) -> bool:
    """True if the JPEG is essentially black/uniform (no data captured)."""
    try:
        arr = np.array(Image.open(io.BytesIO(img_bytes)))
    except Exception:
        return True
    return arr.mean() < 3 and arr.std() < 5


def get_token() -> str:
    r = requests.post(
        TOKEN_URL,
        data={"grant_type": "client_credentials", "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def process_request(token: str, lat: float, lon: float, date_from: str, date_to: str,
                     data_collection: str, evalscript: str, max_cloud_pct: int = 30,
                     mosaicking_order: str = "leastCC") -> bytes | None:
    """Call the Process API to get a rendered image (JPEG bytes)."""
    bbox = [lon - HALF_DEG, lat - HALF_DEG, lon + HALF_DEG, lat + HALF_DEG]
    data_filter: dict = {
        "timeRange": {"from": f"{date_from}T00:00:00Z", "to": f"{date_to}T23:59:59Z"},
        "mosaickingOrder": mosaicking_order,
    }
    if data_collection == "sentinel-2-l2a":
        data_filter["maxCloudCoverage"] = max_cloud_pct
    body = {
        "input": {
            "bounds": {
                "bbox": bbox,
                "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
            },
            "data": [{"type": data_collection, "dataFilter": data_filter}],
        },
        "output": {
            "width": 2048,
            "height": 2048,
            "responses": [{"identifier": "default", "format": {"type": "image/jpeg"}}],
        },
        "evalscript": evalscript,
    }
    r = requests.post(
        PROCESS_URL,
        json=body,
        headers={"Authorization": f"Bearer {token}", "Accept": "image/jpeg"},
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

    incidents = pd.read_csv(INCIDENTS_CSV)
    s3 = boto3.client("s3", region_name="eu-west-3")

    for _, inc in incidents.iterrows():
        inc_id = inc["incident_id"]
        d = datetime.fromisoformat(inc["date_utc"]).date()
        date_from = (d - timedelta(days=WINDOW_DAYS)).isoformat()
        date_to = (d + timedelta(days=WINDOW_DAYS)).isoformat()
        lat = float(inc["lat_approx"])
        lon = float(inc["lon_approx"])
        print(f"\n=== {inc_id}  {d}  ({lat},{lon}) ===", flush=True)

        # Sentinel-2 true color (try widening cloud threshold if first attempt is blank)
        out_s2 = OUT_OPTICAL / f"{inc_id}_truecolor.jpg"
        if not out_s2.exists():
            for cloud_pct in (10, 30, 60, 95):
                print(f"  S2 truecolor (cloud<={cloud_pct}%)...", flush=True)
                img = process_request(token, lat, lon, date_from, date_to,
                                      "sentinel-2-l2a", EVALSCRIPT_S2_TRUECOLOR, max_cloud_pct=cloud_pct)
                if img and len(img) > 5000 and not is_blank(img):
                    out_s2.write_bytes(img)
                    kb = len(img) // 1024
                    print(f"    -> {out_s2} ({kb} KB)", flush=True)
                    s3.upload_file(str(out_s2), DEST_BUCKET, f"optical/sentinel2/{out_s2.name}")
                    break
                elif img:
                    print(f"    blank at cloud<={cloud_pct}, retrying...", flush=True)
            else:
                print(f"    S2 unavailable at all cloud thresholds (Baltic winter cloud cover)", flush=True)
        else:
            print(f"  S2: cache hit", flush=True)

        # Sentinel-1 SAR — try VV/VH first (IW mode), fall back to HH/HV (EW mode)
        out_s1 = OUT_SAR / f"{inc_id}_sar.jpg"
        if not out_s1.exists():
            for label, script in (("VV/VH (IW)", EVALSCRIPT_S1_SAR),
                                   ("HH/HV (EW)", EVALSCRIPT_S1_SAR_HH)):
                print(f"  S1 SAR {label}...", flush=True)
                img = process_request(token, lat, lon, date_from, date_to,
                                      "sentinel-1-grd", script,
                                      mosaicking_order="mostRecent")
                if img and len(img) > 5000:
                    out_s1.write_bytes(img)
                    kb = len(img) // 1024
                    print(f"    -> {out_s1} ({kb} KB)", flush=True)
                    s3.upload_file(str(out_s1), DEST_BUCKET, f"sar/sentinel1/{out_s1.name}")
                    break
            else:
                print(f"    S1 returned no data in either polarization", flush=True)
        else:
            print(f"  S1: cache hit", flush=True)

    print("\nDone.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
