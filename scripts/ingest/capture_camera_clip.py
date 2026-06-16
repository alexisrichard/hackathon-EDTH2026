"""Capture a short sample clip + still frame from a live camera feed.

Encodes the working recipe so nobody re-debugs it during the hackathon:
  - selects a *muxed* HLS format (YouTube live itags 95/94/93 = 720/480/360p);
    plain `-f best` can pick separate video+audio (DASH) and fail to mux.
  - limits duration via the ffmpeg downloader, passing `ffmpeg_i:-t <secs>` as a
    SINGLE argument (split into two tokens it's read as a second download — the
    classic "Fixed output name but more than one file to download" error).
  - extracts a mid-clip JPEG frame.
  - optionally mirrors clip + frame to S3.

S3 retired — writes locally by default; set EDTH_UPLOAD_S3=1 (and pass --s3) to
mirror to your own bucket (was s3://edth2026-baltic/cameras/).

Requires: yt-dlp + ffmpeg available (project .venv has yt-dlp; ffmpeg on PATH).
Works for YouTube live URLs. For JS-player port-cam sites, resolve the .m3u8 in a
browser (DevTools > Network > filter m3u8) and pass that HLS URL instead.

Usage:
  python scripts/ingest/capture_camera_clip.py CAM-KIEL-HOLTENAU \
      "https://www.youtube.com/watch?v=ll6Yep9Va5o" --secs 20 --s3
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

OUT_DIR = Path("data/reference/raw/cameras")
S3_PREFIX = "s3://edth2026-baltic/cameras"

# S3 retired: upload is opt-in. Default OFF so the repo rebuilds locally with no AWS.
UPLOAD_TO_S3 = os.environ.get("EDTH_UPLOAD_S3") == "1"


def ytdlp_cmd() -> list[str]:
    for cand in (Path(".venv/Scripts/python.exe"), Path(".venv/bin/python")):
        if cand.exists():
            return [str(cand.resolve()), "-m", "yt_dlp"]
    return ["yt-dlp"]


def capture(cam_id: str, url: str, secs: int) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    clip = OUT_DIR / f"{cam_id}_sample.mp4"
    cmd = ytdlp_cmd() + [
        "--no-warnings",
        "--force-overwrites",  # else yt-dlp skips an existing file and you get a STALE clip
        "-f", "95/94/93/b[protocol^=m3u8]/b",
        "--downloader", "ffmpeg",
        "--downloader-args", f"ffmpeg_i:-t {secs}",  # ONE arg — never split
        "-o", str(clip),
        url,
    ]
    print("$ " + " ".join(cmd), flush=True)
    rc = subprocess.call(cmd)
    if rc != 0:
        raise SystemExit(f"capture failed (rc={rc}) — feed offline or live ID rotated?")
    return clip


def grab_frame(clip: Path, cam_id: str, at: int) -> Path:
    frame = OUT_DIR / f"{cam_id}_frame.jpg"
    subprocess.call([
        "ffmpeg", "-v", "error", "-y", "-ss", str(at), "-i", str(clip),
        "-frames:v", "1", str(frame),
    ])
    return frame


def upload(paths: list[Path]) -> None:
    for p in paths:
        subprocess.call(["aws", "s3", "cp", str(p), f"{S3_PREFIX}/{p.name}", "--only-show-errors"])
        print(f"  uploaded -> {S3_PREFIX}/{p.name}", flush=True)


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Capture a sample clip + frame from a live camera feed.")
    ap.add_argument("cam_id", help="catalog id, e.g. CAM-KIEL-HOLTENAU")
    ap.add_argument("url", help="YouTube live URL or direct .m3u8 HLS URL")
    ap.add_argument("--secs", type=int, default=20, help="clip length in seconds (default 20)")
    ap.add_argument("--s3", action="store_true", help="upload clip + frame to S3")
    a = ap.parse_args(argv[1:])

    clip = capture(a.cam_id, a.url, a.secs)
    frame = grab_frame(clip, a.cam_id, max(1, a.secs // 2))
    print(f"clip:  {clip}\nframe: {frame}", flush=True)
    if a.s3 and UPLOAD_TO_S3:
        upload([clip, frame])
    elif a.s3:
        print("  --s3 ignored: S3 retired. Set EDTH_UPLOAD_S3=1 to mirror to your own bucket.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
