"""Fetch per-MMSI historical AIS positions from Finnish Digitraffic API.

Use case: the Danish AIS bucket covers the western Baltic well but misses
parts of the Gulf of Finland where most incident vessels operated. The
Digitraffic API at meri.digitraffic.fi has good coverage there but only
supports per-MMSI queries — fine for our ~6 known incident vessels.

License: CC-BY 4.0 (Fintraffic / Digitraffic).

Output: data/ais/digitraffic/<mmsi>_<from>_<to>.json -- raw Digitraffic response
        s3://edth2026-baltic/ais/digitraffic/<mmsi>_<from>_<to>.json
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import boto3
import requests

OUT_DIR = Path("data/ais/digitraffic")
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE = "https://meri.digitraffic.fi/api/ais/v1/locations"

# Known incident vessels. MMSI is the primary identifier in Digitraffic.
# Source: public reporting in data/reference/incidents.csv.
VESSELS = [
    # (label, mmsi or None, imo or None, incident_id, incident_date)
    ("Eagle S",            273347410, 9329760, "INC-2024-12-25", date(2024, 12, 25)),
    ("Fitburg",            None,      None,    "INC-2025-12-31", date(2025, 12, 31)),
    ("Vezhen",             None,      None,    "INC-2025-01-26", date(2025, 1, 26)),
    ("Yi Peng 3",          412419378, 9462108, "INC-2024-11-17", date(2024, 11, 17)),
    ("Newnew Polar Bear",  477959900, 9437301, "INC-2023-10-08", date(2023, 10, 8)),
]

WINDOW_DAYS = 4  # ±4 days around incident


def fetch_mmsi_window(mmsi: int, start_dt: datetime, end_dt: datetime) -> dict | None:
    """Hit Digitraffic for a vessel over a time window. Returns GeoJSON or None."""
    from_ms = int(start_dt.timestamp() * 1000)
    to_ms = int(end_dt.timestamp() * 1000)
    params = {"mmsi": mmsi, "from": from_ms, "to": to_ms}
    try:
        r = requests.get(
            BASE,
            params=params,
            timeout=60,
            headers={
                "User-Agent": "edth2026-baltic-prep/0.1",
                "Accept-Encoding": "gzip",
                "Accept": "application/json",
            },
        )
        if r.status_code == 429:
            print(f"  rate limited; sleeping 30s", flush=True)
            time.sleep(30)
            r = requests.get(BASE, params=params, timeout=60,
                             headers={"User-Agent": "edth2026-baltic-prep/0.1",
                                      "Accept-Encoding": "gzip"})
        if r.status_code != 200:
            print(f"  HTTP {r.status_code}: {r.text[:200]}", flush=True)
            return None
        return r.json()
    except requests.exceptions.RequestException as ex:
        print(f"  request failed: {ex}", flush=True)
        return None


def main() -> int:
    s3 = boto3.client("s3", region_name="eu-west-3")
    bucket = "edth2026-baltic"

    rows_summary: list[dict] = []
    for label, mmsi, imo, inc_id, inc_d in VESSELS:
        print(f"\n=== {label} (MMSI={mmsi}) {inc_id} {inc_d} ===", flush=True)
        if mmsi is None:
            print("  no MMSI known publicly; skipping (would need lookup via Equasis/IMO)", flush=True)
            rows_summary.append({"vessel": label, "mmsi": None, "incident": inc_id,
                                 "status": "skipped_no_mmsi", "feature_count": 0})
            continue
        start_dt = datetime.combine(inc_d - timedelta(days=WINDOW_DAYS), datetime.min.time(), tzinfo=timezone.utc)
        end_dt = datetime.combine(inc_d + timedelta(days=WINDOW_DAYS), datetime.max.time(), tzinfo=timezone.utc)
        result = fetch_mmsi_window(mmsi, start_dt, end_dt)
        if result is None:
            rows_summary.append({"vessel": label, "mmsi": mmsi, "incident": inc_id,
                                 "status": "fetch_failed", "feature_count": 0})
            continue
        feat_count = len(result.get("features", [])) if isinstance(result, dict) else 0
        print(f"  fetched {feat_count} position points", flush=True)

        out_local = OUT_DIR / f"{mmsi}_{inc_d.strftime('%Y%m%d')}.json"
        out_local.write_text(json.dumps(result, indent=1), encoding="utf-8")
        s3.upload_file(str(out_local), bucket, f"ais/digitraffic/{out_local.name}")
        print(f"  saved -> {out_local} + s3://{bucket}/ais/digitraffic/{out_local.name}", flush=True)
        rows_summary.append({"vessel": label, "mmsi": mmsi, "incident": inc_id,
                             "status": "ok", "feature_count": feat_count})

    print("\n=== Summary ===", flush=True)
    for r in rows_summary:
        print(f"  {r['vessel']:20s} MMSI={r['mmsi']}  {r['status']:20s}  features={r['feature_count']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
