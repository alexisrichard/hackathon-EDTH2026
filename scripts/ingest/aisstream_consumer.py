"""AISStream.io live WebSocket consumer for Baltic bbox.

Subscribes to AISStream filtered to the Baltic bounding box, captures messages,
and writes them to disk + S3. Designed to run as a long-lived demo source.

Usage:
  python scripts/ingest/aisstream_consumer.py                # run indefinitely
  python scripts/ingest/aisstream_consumer.py --duration 60  # stop after 60s
  python scripts/ingest/aisstream_consumer.py --duration 60 --max-messages 500

Auth: reads AISSTREAM_API_KEY from .env.local (or env var).
License: AISStream is free for non-commercial development; live-only, no archive
retention rights for redistribution.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import websockets
from dotenv import load_dotenv

# Load .env.local
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env.local")

API_KEY = os.environ.get("AISSTREAM_API_KEY")
if not API_KEY:
    print("ERROR: AISSTREAM_API_KEY not set", file=sys.stderr)
    sys.exit(1)

# Baltic bbox: [[min_lat, min_lon], [max_lat, max_lon]]
BBOX = [[52.0, 9.0], [66.0, 30.0]]

OUT_DIR = Path("data/ais/aisstream")
OUT_DIR.mkdir(parents=True, exist_ok=True)


async def consume(duration: float | None, max_messages: int | None) -> int:
    uri = "wss://stream.aisstream.io/v0/stream"
    subscribe = {
        "APIKey": API_KEY,
        "BoundingBoxes": [BBOX],
        # Default: all message types. Add filters here if needed:
        # "FiltersShipMMSI": [...],
        # "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
    }
    started_at = time.time()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = OUT_DIR / f"baltic_{ts}.jsonl"
    fp = out_path.open("w", encoding="utf-8")
    count = 0

    print(f"Connecting to {uri}", flush=True)
    print(f"Subscribing to bbox {BBOX}", flush=True)
    print(f"Writing to {out_path}", flush=True)
    if duration:
        print(f"Will stop after {duration}s", flush=True)
    if max_messages:
        print(f"Will stop after {max_messages} messages", flush=True)
    print(flush=True)

    try:
        async with websockets.connect(uri, ping_interval=20, ping_timeout=20) as ws:
            await ws.send(json.dumps(subscribe))
            print("Subscribed. Streaming...", flush=True)
            async for msg in ws:
                # websockets returns bytes for binary frames, str for text
                if isinstance(msg, bytes):
                    msg = msg.decode("utf-8", errors="replace")
                fp.write(msg)
                fp.write("\n")
                count += 1
                if count % 50 == 0:
                    elapsed = time.time() - started_at
                    fp.flush()
                    print(f"  msgs={count}  elapsed={elapsed:.0f}s  rate={count/max(elapsed,1):.1f}/s", flush=True)
                # Stop conditions
                if max_messages and count >= max_messages:
                    break
                if duration and (time.time() - started_at) >= duration:
                    break
    except KeyboardInterrupt:
        pass
    finally:
        fp.close()
        elapsed = time.time() - started_at
        print(f"\nDone. Captured {count} messages in {elapsed:.0f}s -> {out_path}", flush=True)
        print(f"  size: {out_path.stat().st_size // 1024} KB", flush=True)
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--duration", type=float, default=None, help="Stop after N seconds")
    p.add_argument("--max-messages", type=int, default=None, help="Stop after N messages")
    args = p.parse_args()
    return asyncio.run(consume(args.duration, args.max_messages))


if __name__ == "__main__":
    sys.exit(main())
