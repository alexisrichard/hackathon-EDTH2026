"""Detect dark vessels in a Sentinel-1 SAR GeoTIFF and cross-reference with AIS.

Pipeline:
  1. Load incident metadata from incidents.csv (or use --scene directly).
  2. Extract VH band (float32 → dB → uint8) with percentile normalization.
  3. Detect ships via YOLOv8 (tiled) with CFAR threshold fallback if YOLO yields nothing.
  4. Load Danish AIS snapshot (±2 h around acquisition) from S3 parquet via DuckDB.
  5. Match detections to AIS within MATCH_KM radius; unmatched = dark vessel.
  6. Write GeoJSON output and print summary.

Detection modes:
  - YOLO (tiled): fine-tuned YOLOv8n on HRSID; good when ship-sea contrast is high
  - CFAR threshold (fallback): finds pixels statistically brighter than local background;
    robust to low-contrast scenes (activated when YOLO yields 0 raw detections)

Usage:
  python scoring/detect_dark_vessels.py                              # default: INC-2024-11-18
  python scoring/detect_dark_vessels.py --incident INC-2022-09-26   # Nord Stream
  python scoring/detect_dark_vessels.py --scene sar/sentinel1/geotiff/INC-2024-11-18_...tif
  python scoring/detect_dark_vessels.py --incident INC-2024-11-18 --conf 0.35 --output out.geojson
  python scoring/detect_dark_vessels.py --incident INC-2024-11-18 --no-yolo  # CFAR only

Note: Danish AIS coverage ends at ~25.9°E.
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import boto3
from botocore.exceptions import ProfileNotFound
import duckdb
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import xy as rio_xy
from scipy import ndimage
from shapely.geometry import Point
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parent.parent

BUCKET          = "edth2026-baltic"
S3_SAR_PREFIX   = "sar/sentinel1/geotiff"
DEFAULT_INC_ID  = "INC-2024-11-18"   # Yi Peng 3 / C-Lion1 — best AIS coverage
DEFAULT_WEIGHTS = ROOT / "scoring" / "weights" / "yolov8n_hrsid_best.pt"

MATCH_KM  = 2.0    # SAR detection within 2 km of AIS position → matched
AREA_DEG  = 0.5    # query radius around incident centroid (≈55 km)
AIS_HOURS = 2      # AIS window ±N hours around SAR acquisition time
VH_PCT_LOW  = 5.0   # percentile lower clip (sea background)
VH_PCT_HIGH = 99.5  # percentile upper clip (ships will be above this → clamp to 255)

# CFAR threshold fallback (works on raw VV float32, dB space)
CFAR_BG_SIGMA  = 60    # gaussian sigma (px) for background — ~1 km at 16 m/px, smooths sea swell
CFAR_SCR_DB    = 8.0   # ship-to-clutter threshold dB; IMO-endorsed Sentinel-1 maritime: 7-10 dB
CFAR_MIN_PX    = 4     # minimum blob size (< 4 px = speckle / sea clutter)
CFAR_MAX_PX    = 500   # maximum blob size (> 500 px = coastline / land feature)
CFAR_EDGE_PX   = 20    # exclude detections within this many pixels of image edge (boundary artifacts)


def load_incident(inc_id: str) -> dict:
    with open(ROOT / "data" / "reference" / "incidents.csv") as f:
        for row in csv.DictReader(f):
            if row["incident_id"] == inc_id:
                return row
    raise ValueError(f"Incident {inc_id} not found in incidents.csv")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--incident", default=DEFAULT_INC_ID,
                   help=f"Incident ID from incidents.csv (default: {DEFAULT_INC_ID})")
    p.add_argument("--scene",   default=None,
                   help="S3 key of a specific GeoTIFF (overrides auto-selection)")
    p.add_argument("--weights", default=str(DEFAULT_WEIGHTS))
    p.add_argument("--conf",    type=float, default=0.20)
    p.add_argument("--no-yolo", action="store_true",
                   help="Skip YOLO, use CFAR threshold detection only")
    p.add_argument("--output",  default="detections_dark_vessels.geojson")
    return p.parse_args()


def s3_client() -> boto3.client:
    """S3 client for the project bucket region (eu-west-3).

    Prefers the shared ``edth2026`` profile when present, otherwise falls back
    to the default credential chain (AWS_PROFILE / default profile / env vars),
    so the script runs on any machine set up per AGENTS.md §2 (`aws configure`)
    without requiring a named profile.
    """
    try:
        session = boto3.Session(profile_name="edth2026")
        if session.get_credentials() is not None:
            return session.client("s3", region_name="eu-west-3")
    except ProfileNotFound:
        pass
    return boto3.Session().client("s3", region_name="eu-west-3")


# ── Scene selection ────────────────────────────────────────────────────────────

def parse_scene_dt(s3_key: str) -> datetime:
    dt_str = Path(s3_key).stem.split("_")[1]   # "2024-12-22T044207"
    return datetime.strptime(dt_str, "%Y-%m-%dT%H%M%S").replace(tzinfo=timezone.utc)


def select_scene(s3: boto3.client, ref_date: datetime, inc_id: str) -> str:
    resp = s3.list_objects_v2(Bucket=BUCKET, Prefix=f"{S3_SAR_PREFIX}/{inc_id}")
    keys = [o["Key"] for o in resp.get("Contents", []) if o["Key"].endswith(".tif")
            and "_vh8bit" not in o["Key"]]
    if not keys:
        raise RuntimeError(
            f"No GeoTIFF found on S3 under {S3_SAR_PREFIX}/{inc_id}. "
            f"Run: python scripts/ingest/fetch_incident_sentinel1_geotiff.py {inc_id}"
        )
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
        vh_db     = 10 * np.log10(np.maximum(vh, 1e-5))
        valid     = vh_db[vh > 1e-5]   # exclude nodata zeros
        p_low     = float(np.percentile(valid, VH_PCT_LOW))
        p_high    = float(np.percentile(valid, VH_PCT_HIGH))
        print(f"  VH dB range: {p_low:.1f} → {p_high:.1f} dB  (scene percentiles)")
        vh_u8 = np.clip((vh_db - p_low) / (p_high - p_low) * 255, 0, 255).astype(np.uint8)
        meta.update(count=1, dtype="uint8")
        with rasterio.open(out, "w", **meta) as dst:
            dst.write(vh_u8, 1)
        print(f"  VH 8-bit saved: {out}")
    else:
        print(f"  VH 8-bit cache hit: {out.name}")
    with rasterio.open(out) as src:
        transform = src.transform
        band = src.read(1)
    return out, transform, band


# ── YOLO inference ────────────────────────────────────────────────────────────

TILE_SIZE   = 800   # matches HRSID training resolution
TILE_STRIDE = 600   # 200px overlap between tiles to avoid missing edge detections
NMS_IOU     = 0.5   # IoU threshold for cross-tile duplicate suppression


def _nms(boxes: np.ndarray, confs: np.ndarray, iou_thr: float) -> tuple[np.ndarray, np.ndarray]:
    """Simple greedy NMS to remove duplicate detections across tile boundaries."""
    if len(boxes) == 0:
        return boxes, confs
    order = confs.argsort()[::-1]
    keep  = []
    while len(order):
        i = order[0]
        keep.append(i)
        if len(order) == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(boxes[i, 0], boxes[rest, 0])
        yy1 = np.maximum(boxes[i, 1], boxes[rest, 1])
        xx2 = np.minimum(boxes[i, 2], boxes[rest, 2])
        yy2 = np.minimum(boxes[i, 3], boxes[rest, 3])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        area_i    = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
        area_rest = (boxes[rest, 2] - boxes[rest, 0]) * (boxes[rest, 3] - boxes[rest, 1])
        iou = inter / (area_i + area_rest - inter + 1e-6)
        order = rest[iou < iou_thr]
    return boxes[keep], confs[keep]


def run_yolo(band: np.ndarray, weights: str, conf: float) -> tuple[np.ndarray, np.ndarray]:
    """Tile the full SAR image into TILE_SIZE×TILE_SIZE chips and run YOLO on each.

    HRSID trains on 800×800 chips; ships are 20-100px in that context.
    Feeding the raw 2048×2048 image at imgsz=800 shrinks ships to 8-40px
    which kills recall. Tiling preserves scale.
    """
    model = YOLO(weights)
    H, W  = band.shape
    all_boxes: list[np.ndarray] = []
    all_confs: list[np.ndarray] = []

    for r0 in range(0, H, TILE_STRIDE):
        for c0 in range(0, W, TILE_STRIDE):
            r1 = min(r0 + TILE_SIZE, H)
            c1 = min(c0 + TILE_SIZE, W)
            tile = band[r0:r1, c0:c1]
            # pad to TILE_SIZE if near edge
            if tile.shape != (TILE_SIZE, TILE_SIZE):
                pad = np.zeros((TILE_SIZE, TILE_SIZE), dtype=tile.dtype)
                pad[:tile.shape[0], :tile.shape[1]] = tile
                tile = pad
            rgb   = np.stack([tile, tile, tile], axis=-1)
            preds = model.predict(rgb, imgsz=TILE_SIZE, conf=conf, verbose=False)[0]
            if len(preds.boxes):
                b = preds.boxes.xyxy.cpu().numpy()
                c = preds.boxes.conf.cpu().numpy()
                # shift box coords back to full-image pixel space
                b[:, [0, 2]] += c0
                b[:, [1, 3]] += r0
                all_boxes.append(b)
                all_confs.append(c)

    if not all_boxes:
        return np.zeros((0, 4)), np.zeros(0)

    boxes = np.concatenate(all_boxes, axis=0)
    confs = np.concatenate(all_confs, axis=0)
    return _nms(boxes, confs, NMS_IOU)


def run_cfar(raw_tif: Path) -> tuple[np.ndarray, np.ndarray]:
    """Maritime ship detection using background subtraction in dB space on VV band.

    Ships in Sentinel-1 VV at C-band appear 5-20 dB above sea background.
    Working in dB space on the raw float32 data makes the SCR threshold
    scene-independent (unlike operating on uint8 after normalization).

    Returns boxes in xyxy pixel format (col=x, row=y) and proxy confidences.
    """
    with rasterio.open(raw_tif) as src:
        vv = src.read(1).astype(np.float32)   # band 1 = VV

    vv_db  = 10.0 * np.log10(np.maximum(vv, 1e-6))

    # Smooth background estimate; nodata (vv≈0) map to -60 dB — dilate to avoid
    # treating nodata edges as targets
    bg_db  = ndimage.gaussian_filter(vv_db, sigma=CFAR_BG_SIGMA)

    # Ship-to-clutter ratio
    scr    = vv_db - bg_db
    detmap = (scr > CFAR_SCR_DB).astype(np.uint8)

    # Remove detections touching nodata (vv == 0) areas
    nodata_mask = (vv < 1e-6)
    nodata_dilated = ndimage.binary_dilation(nodata_mask, iterations=5)
    detmap[nodata_dilated] = 0

    # Exclude image boundary pixels — boundary interpolation artifacts
    H, W = detmap.shape
    edge_mask = np.zeros((H, W), dtype=bool)
    edge_mask[:CFAR_EDGE_PX, :] = True
    edge_mask[-CFAR_EDGE_PX:, :] = True
    edge_mask[:, :CFAR_EDGE_PX] = True
    edge_mask[:, -CFAR_EDGE_PX:] = True
    detmap[edge_mask] = 0

    labeled, n_feat = ndimage.label(detmap)
    if n_feat == 0:
        return np.zeros((0, 4)), np.zeros(0)

    boxes, confs = [], []
    for i in range(1, n_feat + 1):
        mask = labeled == i
        npx  = mask.sum()
        if npx < CFAR_MIN_PX or npx > CFAR_MAX_PX:
            continue
        rows, cols = np.where(mask)
        r0, r1 = rows.min(), rows.max() + 1
        c0, c1 = cols.min(), cols.max() + 1
        peak_scr = float(scr[mask].max())
        conf = min(peak_scr / 15.0, 1.0)  # proxy: 15 dB SCR → full confidence
        boxes.append([c0, r0, c1, r1])    # xyxy format
        confs.append(conf)

    if not boxes:
        return np.zeros((0, 4)), np.zeros(0)
    return np.array(boxes, dtype=np.float32), np.array(confs, dtype=np.float32)


def detections_to_geodataframe(
    boxes: np.ndarray,
    confs: np.ndarray,
    transform: rasterio.transform.Affine,
    lat: float,
    lon: float,
) -> gpd.GeoDataFrame:
    if len(boxes) == 0:
        return gpd.GeoDataFrame({"confidence": [], "geometry": gpd.GeoSeries([], crs="EPSG:4326")},
                                crs="EPSG:4326")
    records = []
    for (x1, y1, x2, y2), conf in zip(boxes, confs):
        col_c = (x1 + x2) / 2
        row_c = (y1 + y2) / 2
        det_lon, det_lat = rio_xy(transform, row_c, col_c)
        records.append({
            "confidence": round(float(conf), 3),
            "geometry":   Point(float(det_lon), float(det_lat)),
        })
    gdf = gpd.GeoDataFrame(records, geometry="geometry", crs="EPSG:4326")
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
    """Query AIS via DuckDB httpfs with predicate pushdown — only filtered rows
    reach RAM instead of downloading full parquet files (~280 MB each)."""
    t_from = scene_dt - timedelta(hours=AIS_HOURS)
    t_to   = scene_dt + timedelta(hours=AIS_HOURS)

    # Collect the S3 paths for the day(s) that overlap the time window
    days_needed = set()
    cur = t_from.date()
    end = t_to.date()
    while cur <= end:
        days_needed.add(cur)
        cur += timedelta(days=1)

    paths = []
    for d in sorted(days_needed):
        paths.append(
            f"s3://edth2026-baltic/ais/parquet/source=danish"
            f"/year={d.year}/month={d.month:02d}/day={d.day:02d}/part-0000.parquet"
        )

    # Pass credentials from the boto3 session into DuckDB
    creds = boto3.Session(profile_name="edth2026").get_credentials().get_frozen_credentials()
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute(f"SET s3_region='eu-west-3'")
    con.execute(f"SET s3_access_key_id='{creds.access_key}'")
    con.execute(f"SET s3_secret_access_key='{creds.secret_key}'")
    if creds.token:
        con.execute(f"SET s3_session_token='{creds.token}'")

    # Danish AIS coverage ends at ~25.9°E — Gulf of Finland (26°E+) is not covered.
    # For GoF incidents, substitute Finnish AIS (Digitraffic) or AISstream.io.
    if lon - AREA_DEG > 25.9:
        print(f"  WARNING: Danish AIS coverage ends at ~25.9°E; "
              f"query area starts at {lon - AREA_DEG:.1f}°E — expect 0 rows.")

    paths_sql = ", ".join(f"'{p}'" for p in paths)
    ts_from = t_from.strftime("%Y-%m-%d %H:%M:%S+00")
    ts_to   = t_to.strftime("%Y-%m-%d %H:%M:%S+00")

    # Parquet already has a pre-computed `ts` TIMESTAMP WITH TIME ZONE column
    query = f"""
        SELECT MMSI, Name, "Ship type", Latitude, Longitude, Timestamp
        FROM read_parquet([{paths_sql}])
        WHERE Latitude  BETWEEN {lat - AREA_DEG} AND {lat + AREA_DEG}
          AND Longitude BETWEEN {lon - AREA_DEG} AND {lon + AREA_DEG}
          AND ts BETWEEN TIMESTAMPTZ '{ts_from}' AND TIMESTAMPTZ '{ts_to}'
    """
    try:
        df = con.execute(query).df()
    except Exception as e:
        print(f"  AIS query failed: {e}", file=sys.stderr)
        print(f"  Paths tried: {paths}", file=sys.stderr)
        return pd.DataFrame(columns=["MMSI", "Name", "Ship type", "Latitude", "Longitude", "ts"])

    if df.empty:
        print("  WARNING: no AIS rows matched — dark-vessel flags will cover all detections.")
        return pd.DataFrame(columns=["MMSI", "Name", "Ship type", "Latitude", "Longitude", "ts"])

    df["ts"] = pd.to_datetime(df["Timestamp"], dayfirst=True, utc=True)
    return df.sort_values("ts").groupby("MMSI").last().reset_index()


# ── Cross-reference ───────────────────────────────────────────────────────────

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = np.radians(lat2 - lat1)
    dlon = np.radians(lon2 - lon1)
    a = np.sin(dlat / 2) ** 2 + np.cos(np.radians(lat1)) * np.cos(np.radians(lat2)) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


_EMPTY_RESULTS_SCHEMA = {
    "det_lat": [], "det_lon": [], "confidence": [], "dark_vessel": [],
    "matched_mmsi": [], "matched_name": [], "dist_km": [],
    "geometry": gpd.GeoSeries([], crs="EPSG:4326"),
}


def cross_reference(detections: gpd.GeoDataFrame, ais_snap: pd.DataFrame) -> gpd.GeoDataFrame:
    if detections.empty:
        return gpd.GeoDataFrame(_EMPTY_RESULTS_SCHEMA, crs="EPSG:4326")
    rows = []
    ais_empty = ais_snap.empty
    for _, det in detections.iterrows():
        det_lat, det_lon = det.geometry.y, det.geometry.x
        best_dist, best_vessel = float("inf"), None
        if not ais_empty:
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
            "dist_km":      round(best_dist, 2) if not np.isinf(best_dist) else None,
            "geometry":     det.geometry,
        })
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    args = parse_args()
    weights = args.weights
    if not args.no_yolo and not Path(weights).exists():
        print(f"ERROR: weights not found at {weights}", file=sys.stderr)
        print("Run: python scoring/train_yolov8_hrsid.py  (or use --no-yolo for CFAR mode)", file=sys.stderr)
        return 1

    # Load incident metadata
    inc     = load_incident(args.incident)
    inc_id  = args.incident
    lat     = float(inc["lat_approx"])
    lon     = float(inc["lon_approx"])
    inc_dt  = datetime.fromisoformat(inc["date_utc"]).replace(tzinfo=timezone.utc)

    print(f"Incident : {inc_id} — {inc['name']}")
    print(f"Location : {lat}°N  {lon}°E")

    s3 = s3_client()

    # 1. Scene selection
    if args.scene:
        s3_key = args.scene
    else:
        print(f"Auto-selecting scene closest to {inc_dt.date()}...", flush=True)
        s3_key = select_scene(s3, inc_dt, inc_id)
    scene_dt = parse_scene_dt(s3_key)
    print(f"Scene    : {Path(s3_key).name}")
    print(f"Acquired : {scene_dt.isoformat()}")

    # 2. Download + preprocess
    raw_tif = download_scene(s3, s3_key)
    _, transform, band = to_vh8bit(raw_tif)

    # 3. Detection
    boxes = np.zeros((0, 4))
    confs = np.zeros(0)
    mode = "CFAR" if args.no_yolo else "YOLO"
    if not args.no_yolo:
        print(f"Running YOLO tiled (conf={args.conf})...", flush=True)
        boxes, confs = run_yolo(band, weights, args.conf)
        print(f"  YOLO raw detections: {len(boxes)}")
        if len(boxes) == 0:
            print("  YOLO found nothing — falling back to CFAR threshold detection", flush=True)
            mode = "CFAR (fallback)"
    if args.no_yolo or len(boxes) == 0:
        print(f"Running CFAR threshold detection...", flush=True)
        boxes, confs = run_cfar(raw_tif)
        print(f"  CFAR raw detections: {len(boxes)}")

    print(f"  Mode: {mode}")
    offshore = detections_to_geodataframe(boxes, confs, transform, lat, lon)
    print(f"  In {inc_id} area: {len(offshore)}")

    # 4. AIS
    print("Loading AIS...", flush=True)
    ais_snap = load_ais_snapshot(s3, scene_dt, lat, lon)
    print(f"  AIS vessels in area (±{AIS_HOURS} h): {len(ais_snap)}")

    # 5. Cross-reference
    results = cross_reference(offshore, ais_snap)
    dark    = results[results["dark_vessel"]]

    print(f"\n{'─'*50}")
    print(f"Detections in area  : {len(results)}")
    print(f"  matched AIS       : {(~results['dark_vessel']).sum()}")
    print(f"  DARK / no AIS     : {len(dark)}")
    if len(dark):
        print("\nDark vessel detections:")
        print(dark[["det_lat", "det_lon", "confidence", "dist_km"]].to_string(index=False))

    # 6. Write GeoJSON
    out_path = Path(args.output)
    if results.empty:
        print("\nNo detections — skipping GeoJSON output.")
    else:
        results.drop(columns=["det_lat", "det_lon"]).to_file(out_path, driver="GeoJSON")
        print(f"\nOutput  : {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
