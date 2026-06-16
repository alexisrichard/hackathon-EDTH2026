"""Visual comparison: base YOLOv8n vs fine-tuned (HRSID) on SAR ship images.

Picks N random validation images, runs both models, and saves a side-by-side
PNG so you can see the improvement at a glance.

Usage:
  python scripts/eval/compare_before_after_finetuning.py
  python scripts/eval/compare_before_after_finetuning.py --n 8 --seed 7 --out comparison.png
"""
from __future__ import annotations

import argparse
import random
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[2]

BASE_WEIGHTS   = ROOT / "data/samples/notebooks/yolov8n.pt"
TUNED_WEIGHTS  = ROOT / "scoring/weights/yolov8n_hrsid_best.pt"
VAL_DIR        = ROOT / "data/hrsid_yolo/images/val"
LABEL_DIR      = ROOT / "data/hrsid_yolo/labels/val"
CONF_THRESHOLD = 0.20


def load_gt_boxes(img_path: Path) -> list[tuple]:
    """Return ground-truth boxes as (cx, cy, w, h) in [0,1] from YOLO label file."""
    label = LABEL_DIR / img_path.with_suffix(".txt").name
    if not label.exists():
        return []
    boxes = []
    for line in label.read_text().splitlines():
        parts = line.strip().split()
        if len(parts) == 5:
            _, cx, cy, w, h = map(float, parts)
            boxes.append((cx, cy, w, h))
    return boxes


def draw_boxes(ax, img: np.ndarray, pred_boxes, title: str):
    """Draw predictions (red) on an axis."""
    ax.imshow(img, cmap="gray")
    ax.set_title(title, fontsize=9, pad=4)
    ax.axis("off")

    for box, conf in pred_boxes:
        x1, y1, x2, y2 = box
        ax.add_patch(mpatches.Rectangle(
            (x1, y1), x2 - x1, y2 - y1,
            linewidth=1.5, edgecolor="#ff4444", facecolor="none",
        ))
        ax.text(x1, y1 - 3, f"{conf:.2f}", color="#ff4444",
                fontsize=7, va="bottom")


def run_inference(model: YOLO, img_path: Path) -> list[tuple]:
    """Return list of (xyxy box, confidence) from model inference."""
    results = model(str(img_path), conf=CONF_THRESHOLD, verbose=False)[0]
    out = []
    for box in results.boxes:
        xyxy = box.xyxy[0].cpu().numpy().tolist()
        conf = float(box.conf[0])
        out.append((xyxy, conf))
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n",    type=int, default=6,  help="Number of images")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--out",  default="comparison_before_after.png")
    args = parser.parse_args()

    random.seed(args.seed)
    all_imgs = sorted(VAL_DIR.glob("*.png"))

    # Prefer images that have at least one ground-truth ship
    imgs_with_ships = [p for p in all_imgs if load_gt_boxes(p)]
    sample = random.sample(imgs_with_ships, min(args.n, len(imgs_with_ships)))

    print(f"Loading base model:   {BASE_WEIGHTS.name}")
    base_model  = YOLO(str(BASE_WEIGHTS))
    print(f"Loading fine-tuned:   {TUNED_WEIGHTS.name}")
    tuned_model = YOLO(str(TUNED_WEIGHTS))

    n = len(sample)
    fig, axes = plt.subplots(n, 2, figsize=(10, 4 * n))
    fig.patch.set_facecolor("#111111")

    col_labels = ["Base YOLOv8n (no fine-tuning)", "Fine-tuned on HRSID (SAR ships)"]
    for col, label in enumerate(col_labels):
        axes[0, col].set_title(label, fontsize=11, color="white", pad=8, fontweight="bold")

    for row, img_path in enumerate(sample):
        img = np.array(Image.open(img_path).convert("RGB"))

        base_preds  = run_inference(base_model,  img_path)
        tuned_preds = run_inference(tuned_model, img_path)

        base_title  = f"{len(base_preds)} detection(s)"
        tuned_title = f"{len(tuned_preds)} detection(s)"

        draw_boxes(axes[row, 0], img, base_preds,  base_title)
        draw_boxes(axes[row, 1], img, tuned_preds, tuned_title)

        for col in range(2):
            axes[row, col].set_facecolor("#111111")

    # Legend
    legend = [mpatches.Patch(color="#ff4444", label="Model prediction")]
    fig.legend(handles=legend, loc="lower center", ncol=1,
               facecolor="#222222", edgecolor="none", labelcolor="white",
               fontsize=10, bbox_to_anchor=(0.5, 0.01))

    fig.suptitle(
        "SAR Ship Detection: Before vs After Fine-tuning on HRSID",
        color="white", fontsize=13, y=1.01,
    )
    plt.tight_layout(rect=[0, 0.03, 1, 1])

    out = Path(args.out)
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    print(f"\nSaved: {out.resolve()}")
    print(f"  {n} images  |  base: {sum(len(run_inference(base_model,p)) for p in sample)} total preds"
          f"  |  tuned: {sum(len(run_inference(tuned_model,p)) for p in sample)} total preds")


if __name__ == "__main__":
    main()
