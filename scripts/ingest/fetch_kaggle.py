"""Download approved Kaggle datasets and mirror them to S3.

Each dataset downloads (zip + auto-extract) into data/reference/raw/kaggle/<slug>/
then syncs to s3://edth2026-baltic/kaggle/<slug>/. Both steps are skip-if-exists
idempotent. Logs license + size + S3 status to
data/reference/kaggle_datasets_INDEX.csv for downstream documentation.

Auth: kaggle CLI reads ~/.kaggle/access_token (or ~/.kaggle/kaggle.json).
S3: uses the ambient AWS credentials (aws configure / ~/.aws/credentials).

Usage:
  python scripts/ingest/fetch_kaggle.py            # download + upload all
  python scripts/ingest/fetch_kaggle.py --skip-s3  # download locally only

Approved list (curated 2026-05-18) — see chat for rationale.
"""
from __future__ import annotations

import csv
import subprocess
import sys
from datetime import datetime
from pathlib import Path

OUT_DIR = Path("data/reference/raw/kaggle")
OUT_DIR.mkdir(parents=True, exist_ok=True)
INDEX_CSV = Path("data/reference/kaggle_datasets_INDEX.csv")

BUCKET = "edth2026-baltic"
S3_PREFIX = f"s3://{BUCKET}/kaggle"


def kaggle_exe() -> str:
    """Prefer the project venv's kaggle, fall back to whatever is on PATH."""
    for cand in (Path(".venv/Scripts/kaggle.exe"), Path(".venv/bin/kaggle")):
        if cand.exists():
            return str(cand.resolve())
    return "kaggle"

# (slug, category, why we want it)
DATASETS: list[tuple[str, str, str]] = [
    # --- User-flagged ---
    ("ubiratanfilho/sds-dataset",                                  "drone_video",     "SeaDronesSee — drone footage with GPS for ship detection"),
    ("piterfm/2022-ukraine-russian-war",                           "geo_context",     "Ukraine-Russia war event database (regional situational context)"),
    ("sanjeetsinghnaik/ship-ports",                                "geo",             "World shipping ports reference"),
    ("kailaspsudheer/sarscope-unveiling-the-maritime-landscape",   "sar_imagery",     "SARScope — labeled SAR maritime imagery"),
    ("jangsienicajzkowy/afo-aerial-dataset-of-floating-objects",   "aerial_imagery",  "AFO — aerial floating-object detection (debris, lifeboats, etc.)"),
    ("arunvithyasegar/daily-port-activity-data-and-trade-estimates","port_activity",   "Daily port activity + trade estimates"),
    # --- SAR (my recommendations) ---
    ("sarribere99/high-resolution-sar-images-dataset-hrsid",       "sar_imagery",     "HRSID — Sentinel-1-derived SAR ship benchmark (5.7 GB)"),
    ("petrarodriguez/ls-ssdd-v1-0",                                "sar_imagery",     "LS-SSDD — large-scene SAR (closest to Sentinel-1 resolution, 2.8 GB)"),
    # --- Optical ---
    ("rhammell/ships-in-satellite-imagery",                        "optical_imagery", "Ships in Satellite Imagery — most-downloaded optical benchmark"),
    # --- AIS ---
    ("eminserkanerdonmez/ais-dataset",                             "ais_sample",      "Kattegat Strait AIS — directly in our Baltic bbox"),
]

# Datasets explicitly skipped (for the audit trail in SOURCES.md):
SKIPPED = [
    ("n0n5ense/global-maritime-pirate-attacks-19932020", "Wrong region — pirate attacks concentrated in Indian Ocean / Gulf of Guinea, ~0 incidents in Baltic"),
    ("pranav941/-sea-of-fishes",                          "Derivable from AIS (look at where ship_type='Fishing' vessels operate)"),
]


def download(slug: str) -> tuple[bool, int, str]:
    target = OUT_DIR / slug.split("/")[1]
    target.mkdir(parents=True, exist_ok=True)
    if any(target.iterdir()):
        # Already downloaded
        size_mb = sum(f.stat().st_size for f in target.rglob("*") if f.is_file()) // 1_048_576
        return True, size_mb, "cache_hit"

    print(f"  downloading {slug}...", flush=True)
    rc = subprocess.call([
        kaggle_exe(), "datasets", "download",
        "-d", slug,
        "-p", str(target),
        "--unzip",
        "--force",
    ])
    if rc != 0:
        return False, 0, f"kaggle CLI exit code {rc}"

    files = list(target.rglob("*"))
    size_mb = sum(f.stat().st_size for f in files if f.is_file()) // 1_048_576
    return True, size_mb, "ok"


def upload_to_s3(slug: str) -> tuple[str, str]:
    """Mirror data/reference/raw/kaggle/<name>/ to s3://.../kaggle/<name>/.

    aws s3 sync is skip-if-exists by size+mtime, so re-runs are cheap. Returns
    (s3_uri, status).
    """
    name = slug.split("/")[1]
    src = OUT_DIR / name
    s3_uri = f"{S3_PREFIX}/{name}/"
    print(f"  syncing -> {s3_uri}", flush=True)
    rc = subprocess.call(["aws", "s3", "sync", str(src), s3_uri, "--only-show-errors"])
    return s3_uri, ("uploaded" if rc == 0 else f"s3 sync exit code {rc}")


def main(argv: list[str]) -> int:
    skip_s3 = "--skip-s3" in argv[1:]
    rows: list[dict] = []
    for slug, category, why in DATASETS:
        print(f"\n=== {slug} ({category}) ===", flush=True)
        ok, size_mb, status = download(slug)
        s3_uri, s3_status = "", "skipped"
        if ok and not skip_s3:
            s3_uri, s3_status = upload_to_s3(slug)
        rows.append({
            "slug": slug,
            "category": category,
            "why": why,
            "size_mb": size_mb,
            "status": status,
            "local_path": str(OUT_DIR / slug.split("/")[1]),
            "s3_uri": s3_uri,
            "s3_status": s3_status,
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        })
        if ok:
            print(f"  {status}  size={size_mb} MB  s3={s3_status}", flush=True)
        else:
            print(f"  FAILED  {status}", flush=True)

    # Append skipped rows for the audit trail
    for slug, reason in SKIPPED:
        rows.append({
            "slug": slug,
            "category": "skipped",
            "why": reason,
            "size_mb": 0,
            "status": "skipped",
            "local_path": "",
            "s3_uri": "",
            "s3_status": "skipped",
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        })

    with INDEX_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "slug", "category", "why", "size_mb", "status", "local_path",
            "s3_uri", "s3_status", "fetched_at",
        ])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\nWrote {INDEX_CSV}", flush=True)

    total_mb = sum(r["size_mb"] for r in rows if r["status"] in ("ok", "cache_hit"))
    print(f"Total: {total_mb} MB across {len(DATASETS)} datasets", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
