"""Generate the brand-matched before/after SAR-detection panels for deck slide 10.

Runs off-the-shelf YOLOv8n vs our HRSID-fine-tuned model on the SAME held-out
SAR tile, draws detections, and writes two aligned panels:
  outreach/deck/assets/model_before.png   (base · red boxes)
  outreach/deck/assets/model_after.png    (fine-tuned · cyan boxes)
"""
from pathlib import Path
import glob
from PIL import Image, ImageDraw, ImageFont
from ultralytics import YOLO

ROOT = Path("/Users/alexisrichard/Documents/Projects/EDTH 2026")
SAMPLES = sorted(glob.glob(str(ROOT / "data/hrsid_samples/*.png")))
OUT = ROOT / "outreach/deck/assets"
CONF = 0.25

# brand palette
VOID = (6, 10, 18); ICE = (232, 241, 248); CYAN = (65, 227, 255)
RED = (255, 69, 56); SLATE = (143, 163, 184); MUTED = (74, 90, 116)
CAP_H = 96

def font(sz, bold=False):
    for p in [
        "/System/Library/Fonts/Supplemental/Courier New Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Courier New.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ]:
        try: return ImageFont.truetype(p, sz)
        except Exception: continue
    return ImageFont.load_default()

def detect(model, path):
    r = model(path, conf=CONF, verbose=False)[0]
    return [b.xyxy[0].tolist() for b in r.boxes]

def panel(img_path, boxes, color, klab, kcount, accent):
    base = Image.open(img_path).convert("L").convert("RGB")
    # darken slightly so neon boxes pop
    base = Image.eval(base, lambda x: int(x * 0.82))
    W, H = base.size
    canvas = Image.new("RGB", (W, H + CAP_H), VOID)
    canvas.paste(base, (0, 0))
    d = ImageDraw.Draw(canvas)
    for x1, y1, x2, y2 in boxes:
        d.rectangle([x1, y1, x2, y2], outline=color, width=3)
    # caption bar
    d.line([(0, H), (W, H)], fill=accent, width=3)
    d.text((22, H + 20), klab, font=font(26, True), fill=accent)
    cnt = f"{kcount} ship{'s' if kcount != 1 else ''} detected"
    f2 = font(30, True)
    tw = d.textlength(cnt, font=f2)
    d.text((W - tw - 22, H + 26), cnt, font=f2, fill=color)
    return canvas

def main():
    base_m = YOLO("yolov8n.pt")
    tuned_m = YOLO(str(ROOT / "scoring/weights/yolov8n_hrsid_best.pt"))

    scored = []
    for p in SAMPLES:
        b = detect(base_m, p); t = detect(tuned_m, p)
        scored.append((p, len(b), len(t), b, t))
        print(f"{Path(p).name:42s} base={len(b):3d}  tuned={len(t):3d}")

    # hero = clearest contrast: prefer 18..48 tuned ships (boxes still legible),
    # maximise tuned-minus-base; fall back to overall max tuned.
    clear = [s for s in scored if 18 <= s[2] <= 48]
    pool = clear or scored
    hero = max(pool, key=lambda s: (s[2] - s[1]))
    p, nb, nt, bb, tb = hero
    print(f"\nHERO: {Path(p).name}  base={nb} tuned={nt}")

    OUT.mkdir(parents=True, exist_ok=True)
    panel(p, bb, RED, "OFF-THE-SHELF  ·  YOLOv8n", nb, MUTED).save(OUT / "model_before.png")
    panel(p, tb, CYAN, "FINE-TUNED  ·  HRSID SAR", nt, CYAN).save(OUT / "model_after.png")
    print(f"wrote {OUT/'model_before.png'} and model_after.png  ({nb} vs {nt} ships)")

if __name__ == "__main__":
    main()
