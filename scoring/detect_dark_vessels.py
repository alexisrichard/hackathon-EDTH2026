"""Detect dark vessels in a Sentinel-1 SAR GeoTIFF and cross-reference with AIS.

Pipeline:
  1. Select the S1-GRD scene closest to a given date from S3 (or use --scene).
  2. Extract VH band (float32 → dB → uint8) for YOLO inference.
  3. Run fine-tuned YOLOv8 to detect vessels; convert pixel detections to lat/lon.
  4. Load Danish AIS snapshot (±2 h around acquisition) from S3 parquet.
  5. Match detections to AIS within MATCH_KM radius; unmatched = dark vessel.
  6. Write GeoJSON output and print summary.

Usage:
  python scoring/detect_dark_vessels.py                          # Eagle S defaults
  python scoring/detect_dark_vessels.py --scene sar/sentinel1/geotiff/INC-2024-12-25_2024-12-22T044207_DESCENDING.tif
  python scoring/detect_dark_vessels.py --weights scoring/weights/yolov8n_hrsid_best.pt --conf 0.35 --output out.geojson
"""
from __future__ import annotations

import argparse
import io
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import xy as rio_xy
from shapely.geometry import Point
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent

BUCKET         = "edth2026-baltic"
S3_SAR_PREFIX  = "sar/sentinel1/geotiff"
DEFAULT_INC_ID = "INC-2024-12-25"
DEFAULT_DATE   = datetime(2024, 12, 25, tzinfo=timezone.utc)
DEFAULT_LAT    = 60.30
DEFAULT_LON    = 26.50
DEFAULT_WEIGHTS = ROOT / "scoring" / "weights" / "yolov8n_hrsid_best.pt"

MATCH_KM  = 2.0    # SAR detection within 2 km of AIS position → matched
AREA_DEG  = 0.5    # AIS query radius around incident centroid (≈55 km)
AIS_HOURS = 2      # AIS window ±N hours around SAR acquisition time
VH_DB_MIN = -25.0  # dB stretch lower bound for 8-bit conversion
VH_DB_MAX = 0.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--scene",   default=None, help="S3 key of the GeoTIFF to use (auto-selects if omitted)")
    p.add_argument("--weights", default=str(DEFAULT_WEIGHTS), help="Path to YOLOv8 .pt weights")
    p.add_argument("--conf",    type=float, default=0.30, help="YOLO confidence threshold")
    p.add_argument("--output",  default="detections_dark_vessels.geojson")
    return p.parse_args()


def s3_client() -> boto3.client:
    return boto3.Session(profile_name="edth2026").client("s3", region_name="eu-west-3")


# ── Scene selection ────────────────────────────────────────────────────────────

def parse_scene_dt(s3_key: str) -> datetime:
    dt_str = Path(s3_key).stem.split("_")[1]   # "2024-12-22T044207"
    return datetime.strptime(dt_str, "%Y-%m-%dT%H%M%S").replace(tzinfo=timezone.utc)


def select_scene(s3: boto3.client, ref_date: datetime, inc_id: str) -> str:
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{S3_SAR_PREFIX}/{inc_id}")
    keys = [o["Key"] for o in resp.get("Contents", []) if o["Key"].endswith(".tif")
            and "_vh8bit" not in o["Key"]]
    if not keys:
        raise RuntimeError(f"No GeoTIFF found on S3 under {S3_SAR_PREFIX}/{inc_id}. "
                           "Run: python scripts/ingest/fetch_eagle_s_sentinel1_geotiff.py")
    return min(keys, key=lambda k: abs((parse_scene_dt(k) - ref_date).total_seconds()))


# ── Preprocessing ─────────────────────────────────────────────────────────────

def download_scene(s3: boto3.client, s3_key: str) -> Path:
    local = ROOT / "data" / "sar" / "sentinel1" / "geotiff" / Path(s3_key).name
    local.parent.mkdir(parents=True, exist_ok=True)
    if not local.exists():
        print(f"  Downloading {s3_key}...", flush=True)
        s3.download_file(BUCKET, s3_key, str(local))
    return local


def to_vh8bit(raw_tif: Path) -> tuple[Path, rasterio.transform.Affine]:
    out = raw_tif.with_name(raw_tif.stem + "_vh8bit.tif")
    if not out.exists():
        with rasterio.open(raw_tif) as src:
            vh   = src.read(2).astype(np.float32)
            meta = src.meta.copy()
        vh_db = 10 * np.log10(np.maximum(vh, 1e-5))
        vh_u8 = np.clip((vh_db - VH_DB_MIN) / (VH_DB_MAX - VH_DB_MIN) * 255, 0, 255).astype(np.uint8)
        meta.update(count=1, dtype="uint8")
        with rasterio.open(out, "w", **meta) as dst:
            dst.write(vh_u8, 1)
        print(f"  VH 8-bit saved: {out}")
    with rasterio.open(out) as src:
        transform = src.transform
        band = src.read(1)
    return out, transform, band


# ── YOLO inference ────────────────────────────────────────────────────────────

def run_yolo(band: np.ndarray, weights: str, conf: float) -> tuple[np.ndarray, np.ndarray]:
    model = YOLO(weights)
    rgb   = np.stack([band, band, band], axis=-1)
    preds = model.predict(rgb, imgsz=band.shape[0], conf=conf, verbose=False)[0]
    boxes = preds.boxes.xyxy.cpu().numpy()
    confs = preds.boxes.conf.cpu().numpy()
    return boxes, confs


def detections_to_geodataframe(
    boxes: np.ndarray,
    confs: np.ndarray,
    transform: rasterio.transform.Affine,
    lat: float,
    lon: float,
) -> gpd.GeoDataFrame:
    records = []
    for (x1, y1, x2, y2), conf in zip(boxes, confs):
        col_c = (x1 + x2) / 2
        row_c = (y1 + y2) / 2
        det_lon, det_lat = rio_xy(transform, row_c, col_c)
        records.append({
            "confidence": round(float(conf), 3),
            "geometry":   Point(float(det_lon), float(det_lat)),
        })
    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    # keep only detections within AREA_DEG of incident centroid
    return gdf[
        gdf.geometry.y.between(lat - AREA_DEG, lat + AREA_DEG) &
        gdf.geometry.x.between(lon - AREA_DEG, lon + AREA_DEG)
    ].copy()


# ── AIS loading ───────────────────────────────────────────────────────────────

def load_ais_snapshot(
    s3: boto3.client,
    scene_dt: datetime,
    lat: float,
    lon: float,
) -> pd.DataFrame:
    dfs = []
    for delta in (-1, 0, 1):
        d = (scene_dt + timedelta(days=delta)).date()
        key = f"ais/parquet/source=danish/year={d.year}/month={d.month:02d}/day={d.day:02d}/part-0000.parquet"
        try:
            raw = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
            dfs.append(pd.read_parquet(io.BytesIO(raw)))
        except s3.exceptions.NoSuchKey:
            print(f"  AIS missing: {key} — run: python scripts/ingest/danish_ais.py date {d}")

    if not dfs:
        print("WARNING: no AIS data found — dark-vessel flags will cover all SAR detections.",
              file=sys.stderr)
        return pd.DataFrame(columns=["MMSI", "Name", "Ship type", "Latitude", "Longitude", "ts"])

    ais = pd.concat(dfs, ignore_index=True)
    ais["ts"] = pd.to_datetime(ais["Timestamp"], dayfirst=True, utc=True)
    t0 = pd.Timestamp(scene_dt)
    ais = ais[
        ais["Latitude"].between(lat - AREA_DEG, lat + AREA_DEG) &
        ais["Longitude"].between(lon - AREA_DEG, lon + AREA_DEG) &
        ais["ts"].between(t0 - pd.Timedelta(hours=AIS_HOURS), t0 + pd.Timedelta(hours=AIS_HOURS))
    ]
    return ais.sort_values("ts").groupby("MMSI").last().reset_index()


# ── Cross-reference ───────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


def cross_reference(detections: gpd.GeoDataFrame, ais_snap: pd.DataFrame) -> gpd.GeoDataFrame:
    rows = []
    for _, det in detections.iterrows():
        det_lat, det_lon = det.geometry.y, det.geometry.x
        best_dist, best_vessel = float("inf"), None
        for _, v in ais_snap.iterrows():
            d = haversine_km(det_lat, det_lon, float(v["Latitude"]), float(v["Longitude"]))
            if d < best_dist:
                best_dist, best_vessel = d, v
        matched = best_dist < MATCH_KM and best_vessel is not None
        rows.append({
            "det_lat":      det_lat,
            "det_lon":      det_lon,
            "confidence":   det["confidence"],
            "dark_vessel":  not matched,
            "matched_mmsi": int(best_vessel["MMSI"]) if matched else None,
            "matched_name": best_vessel["Name"]       if matched else None,
            "dist_km":      round(best_dist, 2),
            "geometry":     det.geometry,
        })
    return gpd.GeoDataFrame(rows, crs="EPSG:4326")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    args = parse_args()
    weights = args.weights
    if not Path(weights).exists():
        print(f"ERROR: weights not found at {weights}", file=sys.stderr)
        print("Run: python scoring/train_yolov8_hrsid.py", file=sys.stderr)
        return 1

    s3 = s3_client()

    # 1. Scene selection
    if args.scene:
        s3_key = args.scene
    else:
        print(f"Auto-selecting scene closest to {DEFAULT_DATE.date()}...", flush=True)
        s3_key = select_scene(s3, DEFAULT_DATE, DEFAULT_INC_ID)
    scene_dt = parse_scene_dt(s3_key)
    print(f"Scene    : {Path(s3_key).name}")
    print(f"Acquired : {scene_dt.isoformat()}")

    # 2. Download + preprocess
    raw_tif = download_scene(s3, s3_key)
    _, transform, band = to_vh8bit(raw_tif)

    # 3. YOLO inference
    print(f"Running YOLO (conf={args.conf})...", flush=True)
    boxes, confs = run_yolo(band, weights, args.conf)
    print(f"  Raw detections: {len(boxes)}")

    offshore = detections_to_geodataframe(boxes, confs, transform, DEFAULT_LAT, DEFAULT_LON)
    print(f"  In Eagle S area: {len(offshore)}")

    # 4. AIS
    print("Loading AIS...", flush=True)
    ais_snap = load_ais_snapshot(s3, scene_dt, DEFAULT_LAT, DEFAULT_LON)
    print(f"  AIS vessels in area (±{AIS_HOURS} h): {len(ais_snap)}")

    # 5. Cross-reference
    results = cross_reference(offshore, ais_snap)
    dark    = results[results["dark_vessel"]]

    print(f"\n{'─'*50}")
    print(f"Offshore detections : {len(results)}")
    print(f"  matched AIS       : {(~results['dark_vessel']).sum()}")
    print(f"  DARK / no AIS     : {len(dark)}")
    if len(dark):
        print("\nDark vessel detections:")
        print(dark[["det_lat", "det_lon", "confidence", "dist_km"]].to_string(index=False))

    # 6. Write GeoJSON
    out_path = Path(args.output)
    results.drop(columns=["det_lat", "det_lon"]).to_file(out_path, driver="GeoJSON")
    print(f"\nOutput  : {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
