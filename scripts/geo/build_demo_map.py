"""Build a Folium demo map for two incidents: C-Lion1 (Yi Peng 3) and Nord Stream.

Outputs:
  demo_map_yi_peng3.html    — Yi Peng 3 AIS track + C-Lion1 cable + Nov 18/19 SAR tile
  demo_map_nordstream.html  — Nord Stream AIS area vessels + Sep 26 SAR tile

Usage:
  python scripts/geo/build_demo_map.py
  python scripts/geo/build_demo_map.py --incident INC-2024-11-18
  python scripts/geo/build_demo_map.py --incident INC-2022-09-26
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
import duckdb
import folium
import numpy as np
import rasterio
from rasterio.transform import xy as rio_xy

ROOT = Path(__file__).resolve().parents[2]

YI_PENG3_MMSI = 414270000

# Approximate cable routes (WGS-84 waypoints) for map display
CABLE_CLION1 = [   # C-Lion1: Helsinki → Rostock (simplified midpoint from Baltic)
    (60.1, 25.0), (59.0, 23.5), (57.5, 20.5), (56.0, 18.0),
    (55.0, 16.0), (54.5, 14.5), (54.2, 12.5), (54.1, 12.1),
]
CABLE_BCS = [      # BCS East-West: Laivkalne (Latvia) → Nybro (Sweden)
    (56.5, 21.0), (56.0, 19.5), (55.8, 18.5), (55.5, 17.5),
    (55.3, 17.0), (56.0, 16.0), (56.5, 15.2), (56.9, 14.8),
]
CABLE_NORDSTREAM = [  # Nord Stream 1+2: approx Russia→Germany route (explosions NE of Bornholm)
    (55.5, 15.4), (55.0, 15.0), (54.8, 14.5),
]


def s3_client():
    return boto3.Session(profile_name="edth2026").client("s3", region_name="eu-west-3")


def duckdb_con():
    creds = boto3.Session(profile_name="edth2026").get_credentials().get_frozen_credentials()
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET s3_region='eu-west-3'")
    con.execute(f"SET s3_access_key_id='{creds.access_key}'")
    con.execute(f"SET s3_secret_access_key='{creds.secret_key}'")
    if creds.token:
        con.execute(f"SET s3_session_token='{creds.token}'")
    return con


def s3_parquet_paths(dates: list) -> list[str]:
    return [
        f"s3://edth2026-baltic/ais/parquet/source=danish"
        f"/year={d.year}/month={d.month:02d}/day={d.day:02d}/part-0000.parquet"
        for d in dates
    ]


# ── Yi Peng 3 track ───────────────────────────────────────────────────────────

def fetch_yi_peng3_track(con, days_range: list) -> list[tuple]:
    """Return list of (ts, lat, lon) sorted chronologically for Yi Peng 3."""
    paths = s3_parquet_paths(days_range)
    paths_sql = ", ".join(f"'{p}'" for p in paths)
    q = f"""
        SELECT ts, Latitude, Longitude
        FROM read_parquet([{paths_sql}])
        WHERE MMSI = {YI_PENG3_MMSI}
          AND Latitude  BETWEEN 50.0 AND 65.0
          AND Longitude BETWEEN 10.0 AND 30.0
        ORDER BY ts
    """
    df = con.execute(q).df()
    print(f"  Yi Peng 3 AIS points: {len(df)}")
    return list(zip(df["ts"], df["Latitude"], df["Longitude"]))


# ── AIS snapshot at scene time ─────────────────────────────────────────────────

def fetch_area_ais(con, scene_dt: datetime, lat: float, lon: float,
                   area_deg: float = 0.5, hours: int = 2):
    days = set()
    for h in range(-hours, hours + 1):
        d = (scene_dt + timedelta(hours=h)).date()
        days.add(d)
    paths = s3_parquet_paths(sorted(days))
    paths_sql = ", ".join(f"'{p}'" for p in paths)
    t0 = (scene_dt - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S+00")
    t1 = (scene_dt + timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M:%S+00")
    q = f"""
        SELECT MMSI, Name, "Ship type", Latitude, Longitude, ts
        FROM read_parquet([{paths_sql}])
        WHERE Latitude  BETWEEN {lat - area_deg} AND {lat + area_deg}
          AND Longitude BETWEEN {lon - area_deg} AND {lon + area_deg}
          AND ts BETWEEN TIMESTAMPTZ '{t0}' AND TIMESTAMPTZ '{t1}'
        ORDER BY ts
    """
    try:
        df = con.execute(q).df()
    except Exception as e:
        print(f"  AIS query failed: {e}", file=sys.stderr)
        return None
    if df.empty:
        return None
    return df.sort_values("ts").groupby("MMSI").last().reset_index()


# ── SAR tile overlay ──────────────────────────────────────────────────────────

def sar_to_png(tif_path: Path, out_png: Path) -> tuple[list, list] | None:
    """Convert vh8bit GeoTIFF to PNG for Folium image overlay.
    Returns (bounds [[S,W],[N,E]], image_path) or None."""
    try:
        from PIL import Image
    except ImportError:
        print("  Pillow not available — skipping SAR overlay")
        return None

    if not tif_path.exists():
        print(f"  SAR tile not found: {tif_path.name}")
        return None

    with rasterio.open(tif_path) as src:
        band = src.read(1)
        bounds = src.bounds

    # RGBA: grayscale + alpha channel (0=transparent for nodata)
    alpha = np.where(band > 0, 200, 0).astype(np.uint8)
    rgba  = np.stack([band, band, band, alpha], axis=-1)
    Image.fromarray(rgba, "RGBA").save(out_png)
    print(f"  SAR PNG: {out_png.name}")
    return [[bounds.bottom, bounds.left], [bounds.top, bounds.right]]


# ── Map builders ─────────────────────────────────────────────────────────────

def build_yi_peng3_map(out_html: Path):
    print("Building Yi Peng 3 / C-Lion1 map...")
    con = duckdb_con()

    # Track: Nov 14–25
    days = [datetime(2024, 11, d).date() for d in range(14, 26)]
    track = fetch_yi_peng3_track(con, days)

    # AIS snapshot for the Nov 19 SAR scene (05:08 UTC)
    scene_dt = datetime(2024, 11, 19, 5, 8, 41, tzinfo=timezone.utc)
    area_ais  = fetch_area_ais(con, scene_dt, lat=55.0, lon=16.0)

    # Centre map on Yi Peng 3's C-Lion1 crossing area
    m = folium.Map(location=[55.5, 14.5], zoom_start=6, tiles="CartoDB dark_matter")

    # ── Yi Peng 3 track ────────────────────────────────────────────────────────
    if track:
        coords = [(lat, lon) for _, lat, lon in track]
        folium.PolyLine(
            coords, color="#ff6600", weight=3, opacity=0.9,
            tooltip="Yi Peng 3 AIS track (first detected Nov 18 06:01 UTC → anchored Nov 25)",
        ).add_to(m)

        # ── Key AIS markers ────────────────────────────────────────────────────
        # First AIS detection (Danish AIS picks up at 16.27°E)
        first = track[0]
        folium.Marker(
            [first[1], first[2]],
            icon=folium.Icon(color="orange", icon="question-sign"),
            tooltip="First Danish AIS detection — Nov 18 06:01 UTC",
            popup=(
                "<b>Yi Peng 3 — First Danish AIS Detection</b><br>"
                "Nov 18, 2024  06:01 UTC<br>"
                f"{first[1]:.4f}°N  {first[2]:.4f}°E<br>"
                "SOG: 7.3 kn  COG: 254° (WSW)<br>"
                "<br><i>East of this point: outside Danish AIS coverage.<br>"
                "BCS East-West cable was cut on Nov 17 at ~17.5°E<br>"
                "(before entering coverage).</i>"
            ),
        ).add_to(m)

        # C-Lion1 crossing — track point closest to 08:00 UTC Nov 18
        target_ts = datetime(2024, 11, 18, 8, 0, tzinfo=timezone.utc)
        clion_pt  = min(track, key=lambda x: abs((x[0] - target_ts).total_seconds()))
        folium.CircleMarker(
            [clion_pt[1], clion_pt[2]], radius=14, color="#ff0000",
            fill=True, fill_color="#ff2200", fill_opacity=0.85,
            tooltip="C-Lion1 crossing — Nov 18 ~08:00 UTC",
            popup=(
                "<b>C-Lion1 Cable Cut — Yi Peng 3 Position</b><br>"
                f"AIS time: {clion_pt[0]}<br>"
                f"{clion_pt[1]:.4f}°N  {clion_pt[2]:.4f}°E<br>"
                "SOG ~7.3 kn  COG ~255°<br>"
                "<br><i>Cable cut confirmed Nov 18 ~08:00 UTC.<br>"
                "Yi Peng 3 AIS track passes directly over the cable route.</i>"
            ),
        ).add_to(m)

        # Kattegat anchor (final position, detained for investigation)
        last = track[-1]
        folium.Marker(
            [last[1], last[2]],
            icon=folium.Icon(color="red", icon="anchor"),
            tooltip="Yi Peng 3 anchored — Kattegat (detained for investigation)",
            popup=(
                "<b>Yi Peng 3 — Kattegat Anchor</b><br>"
                f"Since ~Nov 25, 2024<br>"
                f"{last[1]:.4f}°N  {last[2]:.4f}°E<br>"
                "SOG: 0.1 kn (anchored)<br>"
                "<br><i>Vessel detained by Swedish coast guard.<br>"
                "Multi-national investigation launched.</i>"
            ),
        ).add_to(m)

    # ── Cable routes ──────────────────────────────────────────────────────────
    folium.PolyLine(
        CABLE_CLION1, color="#00ccff", weight=2.5, dash_array="6 4",
        tooltip="C-Lion1 cable (Helsinki → Rostock, ~1200 km)",
    ).add_to(m)
    folium.PolyLine(
        CABLE_BCS, color="#00ff88", weight=2.5, dash_array="6 4",
        tooltip="BCS East-West cable (Lithuania → Sweden, ~218 km)",
    ).add_to(m)

    # ── Incident markers (approximate cable damage points) ────────────────────
    folium.CircleMarker(
        [55.30, 17.50], radius=12, color="#ffcc00", fill=True,
        fill_color="#ffcc00", fill_opacity=0.5,
        tooltip="BCS East-West cut (Nov 17 ~02:00 UTC) — Yi Peng 3 outside AIS coverage here",
        popup=(
            "<b>BCS East-West Cable Cut</b><br>"
            "Nov 17, 2024  ~02:00 UTC<br>"
            "55.30°N  17.50°E (approx cable segment midpoint)<br>"
            "<br><i>Yi Peng 3 was outside Danish AIS coverage at this longitude.<br>"
            "Suspected anchor-drag pattern.</i>"
        ),
    ).add_to(m)
    folium.CircleMarker(
        [55.70, 16.00], radius=12, color="#ff0000", fill=True,
        fill_color="#ff0000", fill_opacity=0.5,
        tooltip="C-Lion1 cut zone — Yi Peng 3 AIS confirmed here ~08:00 UTC",
        popup=(
            "<b>C-Lion1 Cable Cut Zone</b><br>"
            "Nov 18, 2024  ~08:00 UTC<br>"
            "~55.70°N  ~16.0°E<br>"
            "<br><i>Yi Peng 3 AIS track crosses the cable route at this time.<br>"
            "Cable outage confirmed by Cinia (Finland) at ~08:05 UTC.</i>"
        ),
    ).add_to(m)

    # ── AIS vessel markers at SAR acquisition time ────────────────────────────
    if area_ais is not None:
        for _, row in area_ais.iterrows():
            folium.CircleMarker(
                [row["Latitude"], row["Longitude"]],
                radius=5, color="#aaaaaa", fill=True, fill_opacity=0.7,
                tooltip=f"{row['Name']} ({row['Ship type']}) — AIS at SAR acquisition",
            ).add_to(m)

    # SAR overlay
    vh8bit = ROOT / "data" / "sar" / "sentinel1" / "geotiff" / \
             "INC-2024-11-18_2024-11-19T050841_DESCENDING_vh8bit.tif"
    sar_png = out_html.parent / "sar_clion1.png"
    bounds  = sar_to_png(vh8bit, sar_png)
    if bounds:
        folium.raster_layers.ImageOverlay(
            str(sar_png), bounds=bounds, opacity=0.6,
            name="Sentinel-1 SAR (Nov 19 05:08 UTC)",
        ).add_to(m)

    folium.LayerControl().add_to(m)
    m.save(str(out_html))
    print(f"  Saved: {out_html}")


def build_nordstream_map(out_html: Path):
    print("Building Nord Stream map...")
    con = duckdb_con()

    # AIS: vessels in area ±3 days of Sep 26 2022
    scene_dt = datetime(2022, 9, 29, 16, 36, 54, tzinfo=timezone.utc)
    area_ais  = fetch_area_ais(con, scene_dt, lat=55.5, lon=15.4, area_deg=0.8, hours=6)

    m = folium.Map(location=[55.5, 15.4], zoom_start=9, tiles="CartoDB dark_matter")

    folium.PolyLine(
        CABLE_NORDSTREAM, color="#ff6600", weight=2, dash_array="4 4",
        tooltip="Nord Stream pipeline (approx)",
    ).add_to(m)

    # Explosion sites
    for label, lat, lon in [
        ("NS1 leak NE (Sep 26 19:03 UTC)", 55.53, 15.62),
        ("NS1 leak SW (Sep 26 02:03 UTC)", 55.43, 15.36),
        ("NS2 leak (Sep 26 02:03 UTC)",    55.40, 15.34),
    ]:
        folium.CircleMarker(
            [lat, lon], radius=14, color="#ff0000", fill=True,
            fill_color="#ff0000", fill_opacity=0.6,
            tooltip=f"💥 {label}",
        ).add_to(m)

    # AIS vessels in area at SAR acquisition time
    if area_ais is not None:
        print(f"  Vessels in area: {len(area_ais)}")
        for _, row in area_ais.iterrows():
            name = row["Name"] if row["Name"] else "Unknown"
            folium.CircleMarker(
                [row["Latitude"], row["Longitude"]],
                radius=6, color="#00ccff", fill=True, fill_opacity=0.8,
                tooltip=f"{name} ({row['Ship type']}) MMSI {row['MMSI']}",
                popup=f"MMSI: {row['MMSI']}<br>Name: {name}<br>Type: {row['Ship type']}",
            ).add_to(m)

    # SAR overlay
    vh8bit = ROOT / "data" / "sar" / "sentinel1" / "geotiff" / \
             "INC-2022-09-26_2022-09-29T163654_ASCENDING_vh8bit.tif"
    sar_png = out_html.parent / "sar_nordstream.png"
    bounds  = sar_to_png(vh8bit, sar_png)
    if bounds:
        folium.raster_layers.ImageOverlay(
            str(sar_png), bounds=bounds, opacity=0.55,
            name="Sentinel-1 SAR (Sep 29 16:37 UTC)",
        ).add_to(m)

    folium.LayerControl().add_to(m)
    m.save(str(out_html))
    print(f"  Saved: {out_html}")


# ── Main ─────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--incident", default=None,
                   help="INC-2024-11-18 or INC-2022-09-26 (default: both)")
    return p.parse_args()


def main():
    args = parse_args()
    out_dir = ROOT

    if args.incident is None or args.incident == "INC-2024-11-18":
        build_yi_peng3_map(out_dir / "demo_map_yi_peng3.html")

    if args.incident is None or args.incident == "INC-2022-09-26":
        build_nordstream_map(out_dir / "demo_map_nordstream.html")


if __name__ == "__main__":
    main()
