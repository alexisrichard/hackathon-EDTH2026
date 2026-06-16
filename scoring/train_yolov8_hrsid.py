"""Fine-tune YOLOv8n on HRSID for SAR ship detection.

Expects the dataset to be prepared first:
  python scripts/ingest/prepare_hrsid_dataset.py

Outputs best weights to:
  scoring/runs/yolov8n_ship/weights/best.pt

Usage:
  python scoring/train_yolov8_hrsid.py [--epochs N] [--batch N] [--imgsz N]

Weights are also copied to scoring/weights/yolov8n_hrsid_best.pt for use by
detect_dark_vessels.py.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parent.parent

YAML_PATH     = ROOT / "scoring" / "hrsid.yaml"
WEIGHTS_DIR   = ROOT / "scoring" / "weights"
FINAL_WEIGHTS = WEIGHTS_DIR / "yolov8n_hrsid_best.pt"
TRAIN_PROJECT = ROOT / "scoring" / "runs"
TRAIN_NAME    = "yolov8n_ship"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Fine-tune YOLOv8n on HRSID")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--batch",  type=int, default=8)
    p.add_argument("--imgsz",  type=int, default=800, help="HRSID tiles are natively 800×800")
    p.add_argument("--patience", type=int, default=15, help="Early-stopping patience (epochs)")
    return p.parse_args()


def pick_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


def main() -> int:
    args = parse_args()

    if not YAML_PATH.exists():
        print(f"ERROR: {YAML_PATH} not found.", file=sys.stderr)
        print("Run: python scripts/ingest/prepare_hrsid_dataset.py", file=sys.stderr)
        return 1

    from ultralytics import YOLO  # noqa: PLC0415 — import after arg parse to fail fast

    device = pick_device()
    print(f"Device  : {device}")
    print(f"Dataset : {YAML_PATH}")
    print(f"Epochs  : {args.epochs}  batch={args.batch}  imgsz={args.imgsz}", flush=True)

    model = YOLO("yolov8n.pt")
    results = model.train(
        data     = str(YAML_PATH),
        epochs   = args.epochs,
        imgsz    = args.imgsz,
        batch    = args.batch,
        device   = device,
        project  = str(TRAIN_PROJECT),
        name     = TRAIN_NAME,
        exist_ok = True,
        patience = args.patience,
        verbose  = True,
    )

    best = TRAIN_PROJECT / TRAIN_NAME / "weights" / "best.pt"
    if not best.exists():
        print("ERROR: best.pt not found after training.", file=sys.stderr)
        return 1

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy(best, FINAL_WEIGHTS)

    map50 = results.results_dict.get("metrics/mAP50(B)", float("nan"))
    print(f"\nmAP50 (val) : {map50:.4f}")
    print(f"Best weights: {FINAL_WEIGHTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
