"""Global Fishing Watch v3 event fetcher — per-vessel queries.

GFW events API requires a vessel filter (bbox-only queries return 422
"deprecated schema"). For each named incident suspect we:
  1. Resolve GFW vesselId(s) via IMO (or name) search
  2. Fetch port-visits, loitering, encounters, gaps, fishing events
     over a wide window (incident date ±90 days)

Outputs:
  data/reference/gfw_vessels/<label>.json   — search results (former-name renames!)
  data/reference/gfw_events/<vesselId>_<event_type>.json — per-vessel events
  data/reference/gfw_vessel_summary.csv     — flat summary table

License: GFW data is free for research with attribution. Token in .env.local.
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import boto3
import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env.local")

TOKEN = os.environ.get("GFW_API_TOKEN")
if not TOKEN:
    print("ERROR: GFW_API_TOKEN missing in .env.local", file=sys.stderr)
    sys.exit(1)

HEADERS = {"Authorization": f"Bearer {TOKEN}"}
BASE = "https://gateway.api.globalfishingwatch.org/v3"

OUT_EVENTS = Path("data/reference/gfw_events")
OUT_VESSELS = Path("data/reference/gfw_vessels")
OUT_EVENTS.mkdir(parents=True, exist_ok=True)
OUT_VESSELS.mkdir(parents=True, exist_ok=True)

# Incident vessels: (label, primary IMO, fallback search query, incident_id, date)
INCIDENT_VESSELS = [
    ("Eagle S",            "9329760", "EAGLE-S",            "INC-2024-12-25", "2024-12-25"),
    ("Yi Peng 3",          "9462108", "YI PENG 3",          "INC-2024-11-17", "2024-11-17"),
    ("Newnew Polar Bear",  "9437301", "NEWNEW POLAR BEAR",  "INC-2023-10-08", "2023-10-08"),
    ("Vezhen",             None,      "VEZHEN",             "INC-2025-01-26", "2025-01-26"),
    ("Fitburg",            None,      "FITBURG",            "INC-2025-12-31", "2025-12-31"),
]

EVENT_DATASETS = [
    ("port_visits",  "public-global-port-visits-events:latest"),
    ("loitering",    "public-global-loitering-events:latest"),
    ("encounters",   "public-global-encounters-events:latest"),
    ("gaps",         "public-global-gaps-events:latest"),
    ("fishing",      "public-global-fishing-events:latest"),
]

WINDOW_DAYS = 90  # wide window — vessel history, not just bbox


def vessel_search(query: str, limit: int = 10) -> list[dict]:
    r = requests.get(
        f"{BASE}/vessels/search",
        headers=HEADERS,
        params={
            "query": query,
            "datasets[0]": "public-global-vessel-identity:latest",
            "limit": limit,
        },
        timeout=30,
    )
    if r.status_code != 200:
        print(f"    vessel search HTTP {r.status_code}: {r.text[:150]}", flush=True)
        return []
    return r.json().get("entries", [])


def fetch_events_for_vessel(vessel_id: str, dataset: str,
                              start: str, end: str) -> list[dict]:
    all_entries: list[dict] = []
    offset = 0
    limit = 200
    while True:
        r = requests.post(
            f"{BASE}/events",
            headers={**HEADERS, "Content-Type": "application/json"},
            params={"limit": limit, "offset": offset},
            json={
                "datasets": [dataset],
                "vessels": [vessel_id],
                "startDate": start,
                "endDate": end,
            },
            timeout=60,
        )
        if r.status_code not in (200, 201):
            print(f"    events HTTP {r.status_code}: {r.text[:150]}", flush=True)
            break
        d = r.json()
        entries = d.get("entries", [])
        all_entries.extend(entries)
        if len(entries) < limit or d.get("nextOffset") is None:
            break
        offset = d["nextOffset"]
    return all_entries


def main() -> int:
    s3 = boto3.client("s3", region_name="eu-west-3")
    summary_rows: list[dict] = []

    for label, imo, name_query, inc_id, inc_date_str in INCIDENT_VESSELS:
        print(f"\n=== {label} ({inc_id}) ===", flush=True)
        # Step 1: vessel registry search — prefer IMO (precise, 1-2 hits).
        # Fall back to name only when no IMO is known (name search is noisy:
        # returns many similar-named unrelated vessels).
        queries = [imo] if imo else [name_query] if name_query else []
        all_hits: list[dict] = []
        for q in queries:
            hits = vessel_search(q)
            print(f"  search('{q}'): {len(hits)} hits", flush=True)
            all_hits.extend(hits)
            time.sleep(0.5)
        # Dedupe by selfReportedInfo[0].id
        unique: dict[str, dict] = {}
        for e in all_hits:
            ssi = e.get("selfReportedInfo") or []
            for s in ssi:
                vid = s.get("id")
                if vid and vid not in unique:
                    unique[vid] = {"entry": e, "info": s}
        print(f"  unique vesselIds: {len(unique)}", flush=True)
        if not unique:
            print(f"  no GFW vessel matches — skipping events", flush=True)
            continue

        # Save the raw search
        vs_file = OUT_VESSELS / f"{label.replace(' ', '_').lower()}.json"
        vs_file.write_text(json.dumps({"label": label, "incident_id": inc_id,
                                        "queries": queries,
                                        "vessels": [v["entry"] for v in unique.values()]}, indent=2),
                            encoding="utf-8")
        s3.upload_file(str(vs_file), "edth2026-baltic", f"reference/gfw_vessels/{vs_file.name}")

        # Step 2: events per vessel
        inc_d = datetime.fromisoformat(inc_date_str).date()
        start = (inc_d - timedelta(days=WINDOW_DAYS)).isoformat()
        end = (inc_d + timedelta(days=WINDOW_DAYS)).isoformat()

        for vid, info in unique.items():
            print(f"  vessel {info['info'].get('shipname','?')} (flag {info['info'].get('flag','?')}, mmsi {info['info'].get('ssvid','?')})", flush=True)
            for ev_label, ds in EVENT_DATASETS:
                out_file = OUT_EVENTS / f"{vid}_{ev_label}.json"
                if out_file.exists() and out_file.stat().st_size > 100:
                    n_cached = len(json.loads(out_file.read_text(encoding="utf-8")).get("entries", []))
                    print(f"    {ev_label:12s}: cache ({n_cached} entries)", flush=True)
                    continue
                entries = fetch_events_for_vessel(vid, ds, start, end)
                payload = {
                    "vesselId": vid,
                    "shipname": info["info"].get("shipname"),
                    "flag": info["info"].get("flag"),
                    "mmsi": info["info"].get("ssvid"),
                    "imo": info["info"].get("imo"),
                    "dataset": ds,
                    "incident_id": inc_id,
                    "start_date": start,
                    "end_date": end,
                    "count": len(entries),
                    "entries": entries,
                }
                out_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
                s3.upload_file(str(out_file), "edth2026-baltic", f"reference/gfw_events/{out_file.name}")
                print(f"    {ev_label:12s}: {len(entries):4d} events  -> {out_file.name}", flush=True)
                summary_rows.append({
                    "incident_id": inc_id,
                    "incident_vessel_label": label,
                    "gfw_vesselId": vid,
                    "shipname": info["info"].get("shipname"),
                    "flag": info["info"].get("flag"),
                    "mmsi": info["info"].get("ssvid"),
                    "imo": info["info"].get("imo"),
                    "event_type": ev_label,
                    "count": len(entries),
                })
                time.sleep(0.3)

    if summary_rows:
        pd.DataFrame(summary_rows).to_csv("data/reference/gfw_vessel_summary.csv", index=False)
        print(f"\nWrote data/reference/gfw_vessel_summary.csv ({len(summary_rows)} rows)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
