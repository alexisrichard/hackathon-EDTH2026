"""Fetch marine weather (wave + wind) for each incident window.

Source: Open-Meteo Marine API (free, no auth required, CC-BY 4.0)
        https://marine-api.open-meteo.com/v1/marine

For each incident in data/reference/incidents.csv, fetch hourly:
  - wave_height (m)
  - wave_period (s)
  - wave_direction (°)
  - wind_wave_height (m)
  - swell_wave_height (m)

For the incident location ±14 days. Outputs one JSON per incident at
data/reference/marine_weather/<incident_id>.json.

Useful as environmental context for behavioral analysis (vessels slow down
naturally in heavy seas — the model will need this).
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

OUT_DIR = Path("data/reference/marine_weather")
OUT_DIR.mkdir(parents=True, exist_ok=True)

INCIDENTS_CSV = Path("data/reference/incidents.csv")
API = "https://marine-api.open-meteo.com/v1/marine"
WIND_API = "https://archive-api.open-meteo.com/v1/archive"
WINDOW_DAYS = 14


def fetch_marine(lat: float, lon: float, start_date: str, end_date: str) -> dict | None:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join([
            "wave_height", "wave_period", "wave_direction",
            "wind_wave_height", "wind_wave_period", "wind_wave_direction",
            "swell_wave_height", "swell_wave_period", "swell_wave_direction",
            "ocean_current_velocity", "ocean_current_direction",
        ]),
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "UTC",
    }
    try:
        r = requests.get(API, params=params, timeout=60,
                         headers={"User-Agent": "edth2026-baltic-prep/0.1"})
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as ex:
        print(f"    marine fetch failed: {ex}", flush=True)
        return None


def fetch_wind(lat: float, lon: float, start_date: str, end_date: str) -> dict | None:
    """Archive-API gives historical wind from ERA5 reanalysis."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join([
            "wind_speed_10m", "wind_direction_10m", "wind_gusts_10m",
            "temperature_2m", "surface_pressure",
        ]),
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "UTC",
    }
    try:
        r = requests.get(WIND_API, params=params, timeout=60,
                         headers={"User-Agent": "edth2026-baltic-prep/0.1"})
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as ex:
        print(f"    wind fetch failed: {ex}", flush=True)
        return None


def main() -> int:
    incidents = pd.read_csv(INCIDENTS_CSV)
    print(f"Fetching marine weather for {len(incidents)} incidents...", flush=True)
    for _, inc in incidents.iterrows():
        inc_id = inc["incident_id"]
        d = datetime.fromisoformat(inc["date_utc"]).date()
        start = (d - timedelta(days=WINDOW_DAYS)).isoformat()
        end = (d + timedelta(days=WINDOW_DAYS)).isoformat()
        lat = inc["lat_approx"]
        lon = inc["lon_approx"]
        print(f"\n[{inc_id}] lat={lat} lon={lon} {start}..{end}", flush=True)

        out_path = OUT_DIR / f"{inc_id}.json"
        if out_path.exists() and out_path.stat().st_size > 1000:
            print(f"  cache hit: {out_path}")
            continue

        marine = fetch_marine(lat, lon, start, end)
        if marine:
            n_marine = len(marine.get("hourly", {}).get("time", []))
            print(f"  marine: {n_marine} hourly samples", flush=True)
        time.sleep(0.5)  # rate-limit politely

        wind = fetch_wind(lat, lon, start, end)
        if wind:
            n_wind = len(wind.get("hourly", {}).get("time", []))
            print(f"  wind/temp: {n_wind} hourly samples", flush=True)

        combined = {
            "incident_id": inc_id,
            "lat": lat,
            "lon": lon,
            "window_start_utc": start,
            "window_end_utc": end,
            "marine": marine,
            "atmosphere": wind,
            "metadata": {
                "marine_source": "Open-Meteo Marine API (CC-BY 4.0)",
                "atmosphere_source": "Open-Meteo Archive (ERA5 reanalysis, CC-BY 4.0)",
                "fetched_at": datetime.utcnow().isoformat() + "Z",
            },
        }
        out_path.write_text(json.dumps(combined, indent=1), encoding="utf-8")
        size_kb = out_path.stat().st_size // 1024
        print(f"  -> {out_path}  {size_kb} KB", flush=True)
        time.sleep(0.5)
    print(f"\nDone. Outputs in {OUT_DIR}/", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
