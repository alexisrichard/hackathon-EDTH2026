"""`/frame` — CONTINUOUS on-demand cueing: the real engine scored at ANY instant.

Wraps `scoring.zone_score` (the exact engine the static demo cues come from) so the
app can show real satellite taskings + per-vessel risk for times *outside* the two
precomputed windows. Returns the same snapshot shape the frontend already renders
(`{at, taskings, risk, dark_contacts, …}`), so no model mapping is needed.

Point-in-time, no look-ahead (the engine only uses data ≤ `at`). Performance: the
first request for a new time scans a 90-day lookback (~seconds); the cable-distance
surface, the parsed tiles (in `zone_score`), and the per-snapped-instant result are
all cached, so repeated/playback requests are instant.
"""

from __future__ import annotations

import gc
import os
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache

import app.core.paths  # noqa: F401  (puts repo root on sys.path before scoring.*)
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["frame"])

# The SW/central Baltic theatre — same bbox as the precomputed scenarios (the
# cut-prone cables + where Danish AIS actually receives). Wider bboxes pull in
# thousands of vessels and blow the per-request budget. Snapping the clock to the
# cadence makes the result cacheable.
BALTIC_BBOX = (12.0, 53.5, 22.0, 60.0)
# Behavioural-prior window. Cold latency is dominated by parsing this many day-tiles
# (lru-cached, so only the FIRST touch of a window pays). 30 keeps a cold scrub ~2-3 s
# (vs ~4-24 s at 60, where the variance was how many tiles were already resident); the
# prior is still multi-week. The live engine is the "always-on" feed — the hero story
# lives in the precomputed windows — so a shorter prior here is the right trade.
LOOKBACK_DAYS = 30
CADENCE_H = 3
N_SAT = 3
STEP = CADENCE_H * 3600
DARK_RECENCY_S = 48 * 3600  # a SAR dark cluster cues us for ~2 days after its pass


@lru_cache(maxsize=1)
def _cable_dist():
    from scoring.zone_score import _cable_distance_fn

    return _cable_distance_fn()


def warm() -> None:
    """Build the cable-distance surface once (≈0.8 s) so the user's first scrub to a
    live instant doesn't pay it. Called off-thread at app startup; safe to no-op if
    the geo layers are missing. Freezes the GC at the end so the import + cable-surface
    objects are excluded from every future collection (see `_warm_lookback`)."""
    try:
        _cable_dist()
    except Exception:  # never let a prewarm failure block startup
        pass
    gc.collect()
    gc.freeze()  # lock the small startup heap into the permanent generation while it's cheap


def _warm_lookback(day: str) -> None:
    """Parse the lookback + cut day-tiles into zone_score's tile cache, then freeze the
    GC, BEFORE the allocation-heavy scoring runs.

    Why: each cold frame builds ~2000 vessel dicts + prior-history lists. With the tile
    cache resident (millions of objects across a 30-day window, accumulating over the
    session) Python's generational GC fires gen-2 sweeps DURING that scoring, each one
    rescanning the whole tile cache — 15 s+ spikes on high-traffic days (measured: 2041
    vessels = 15.7 s, ~11 s of it pure GC). `gc.freeze()` moves the now-resident tiles
    to the permanent generation, excluded from future collections (still refcount-freed
    if the lru cache evicts them), so scoring only ever scans its own small working set.
    Result: a flat ~3 s cold regardless of vessel count."""
    from scoring.zone_score import _tile_paths, _tile_vessels

    start = (date.fromisoformat(day) - timedelta(days=LOOKBACK_DAYS)).isoformat()
    for f in _tile_paths():
        d = os.path.basename(f)[len("tracks_") : -len(".json")]
        if start <= d <= day:
            _tile_vessels(f)
    gc.collect()
    gc.freeze()


@lru_cache(maxsize=1024)
def _frame(at_ts: int) -> dict:
    from scoring.zone_score import (
        _signal_epoch,
        build_theatre,
        load_dark_vessels,
        rank_cues,
    )

    day = datetime.fromtimestamp(at_ts, timezone.utc).strftime("%Y-%m-%d")
    _warm_lookback(day)  # parse + gc.freeze() the tiles before scoring → flat ~3 s cold
    theatre = build_theatre(at_ts, day, BALTIC_BBOX, lookback=LOOKBACK_DAYS)
    dark = [
        x for x in load_dark_vessels()
        if (se := _signal_epoch(x.get("signal_date"))) is not None
        and at_ts - DARK_RECENCY_S <= se <= at_ts
    ]
    taskings = rank_cues(theatre, dark, _cable_dist(), top_n=N_SAT, sensor="SAR")
    risk = {
        str(v["mmsi"]): {
            "name": v["name"], "type": v["type"], "risk": v["vessel_risk"],
            "sar": v["sar"], "live": v["live_anomaly"],
            "confidence": v["breakdown"]["confidence"],
            "prior_days": v["breakdown"]["prior_days"],
            "contributions": v["breakdown"]["contributions"],
            "explanation": v["breakdown"]["explanation"],
        }
        for v in theatre
    }
    return {
        "at": datetime.fromtimestamp(at_ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "at_ts": at_ts, "cadence_h": CADENCE_H, "n_sat": N_SAT,
        "next_retask_ts": at_ts + STEP,
        "dark_contacts": [{"lon": d["lon"], "lat": d["lat"], "confidence": d.get("sar_confidence")} for d in dark],
        "taskings": taskings, "risk": risk,
    }


@router.get("/frame", summary="Continuous on-demand cueing frame at instant t")
def get_frame(at: str = Query(..., description="ISO-8601 UTC instant, e.g. 2023-07-01T12:00:00Z")) -> dict:
    """The real engine's satellite taskings + per-vessel risk at `at` (snapped to the
    re-tasking cadence). Same shape as a precomputed time-series snapshot."""
    try:
        ts = int(datetime.fromisoformat(at.replace("Z", "+00:00")).timestamp())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"bad 'at': {exc}") from exc
    return _frame((ts // STEP) * STEP)
