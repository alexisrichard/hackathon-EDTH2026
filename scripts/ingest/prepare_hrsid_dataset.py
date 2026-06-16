"""Prepare the HRSID dataset for YOLOv8 training.

Downloads Sentinel-1 SAR ship-detection images and COCO annotations from
s3://edth2026-baltic/kaggle/high-resolution-sar-images-dataset-hrsid/,
converts bounding boxes to YOLO format, and writes a dataset YAML ready for
ultralytics training.

Output layout:
  data/hrsid_yolo/
    images/train/   *.png
    images/val/     *.png
    labels/train/   *.txt   (YOLO format: class xc yc w h, normalised)
    labels/val/     *.txt
    hrsid.yaml

Usage:
  python scripts/ingest/prepare_hrsid_dataset.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ProfileNotFound

ROOT = Path(__file__).resolve().parents[2]

BUCKET    = "edth2026-baltic"
S3_PREFIX = "kaggle/high-resolution-sar-images-dataset-hrsid"
OUT_DIR   = ROOT / "data" / "hrsid_yolo"
YAML_PATH = ROOT / "scoring" / "hrsid.yaml"

SPLITS = {
    "train": f"{S3_PREFIX}/annotations/train2017.json",
    "val":   f"{S3_PREFIX}/annotations/test2017.json",
}


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


def load_coco(s3: boto3.client, key: str) -> dict:
    return json.loads(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())


def coco_bbox_to_yolo(bbox: list[float], iw: int, ih: int) -> tuple[float, float, float, float]:
    x, y, w, h = bbox
    return (x + w / 2) / iw, (y + h / 2) / ih, w / iw, h / ih


def prepare_split(s3: boto3.client, split: str, ann_key: str) -> tuple[int, int]:
    coco = load_coco(s3, ann_key)

    annots: dict[int, list] = {}
    for ann in coco["annotations"]:
        annots.setdefault(ann["image_id"], []).append(ann["bbox"])

    img_dir = OUT_DIR / "images" / split
    lbl_dir = OUT_DIR / "labels" / split
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    ok = skip = 0
    for meta in coco["images"]:
        fname  = meta["file_name"]
        iw, ih = meta["width"], meta["height"]
        out_img = img_dir / fname
        out_lbl = lbl_dir / (Path(fname).stem + ".txt")

        if not out_img.exists():
            s3_key = f"{S3_PREFIX}/images/{fname}"
            try:
                data = s3.get_object(Bucket=BUCKET, Key=s3_key)["Body"].read()
                out_img.write_bytes(data)
            except s3.exceptions.NoSuchKey:
                skip += 1
                continue

        with open(out_lbl, "w") as f:
            for bbox in annots.get(meta["id"], []):
                xc, yc, w, h = coco_bbox_to_yolo(bbox, iw, ih)
                f.write(f"0 {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}\n")
        ok += 1

    return ok, skip


def write_yaml() -> None:
    YAML_PATH.parent.mkdir(parents=True, exist_ok=True)
    YAML_PATH.write_text(
        f"path: {OUT_DIR}\n"
        "train: images/train\n"
        "val:   images/val\n"
        "nc: 1\n"
        "names: [ship]\n"
    )


def main() -> int:
    s3 = s3_client()
    for split, ann_key in SPLITS.items():
        print(f"Preparing {split}...", flush=True)
        ok, skip = prepare_split(s3, split, ann_key)
        n_img = len(list((OUT_DIR / "images" / split).glob("*.png")))
        n_lbl = len(list((OUT_DIR / "labels" / split).glob("*.txt")))
        print(f"  {ok} images ready, {skip} missing on S3 | {n_img} imgs / {n_lbl} labels on disk")

    write_yaml()
    print(f"\nDataset YAML written: {YAML_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
