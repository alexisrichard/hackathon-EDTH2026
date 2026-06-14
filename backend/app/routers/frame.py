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

from datetime import datetime, timezone
from functools import lru_cache

import app.core.paths  # noqa: F401  (puts repo root on sys.path before scoring.*)
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(tags=["frame"])

# The SW/central Baltic theatre — same bbox as the precomputed scenarios (the
# cut-prone cables + where Danish AIS actually receives). Wider bboxes pull in
# thousands of vessels and blow the per-request budget. Snapping the clock to the
# cadence makes the result cacheable.
BALTIC_BBOX = (12.0, 53.5, 22.0, 60.0)
LOOKBACK_DAYS = 60   # behavioural prior window; 60 keeps the cold request ~4 s vs ~14 s at 90
CADENCE_H = 3
N_SAT = 3
STEP = CADENCE_H * 3600
DARK_RECENCY_S = 48 * 3600  # a SAR dark cluster cues us for ~2 days after its pass


@lru_cache(maxsize=1)
def _cable_dist():
    from scoring.zone_score import _cable_distance_fn

    return _cable_distance_fn()


@lru_cache(maxsize=1024)
def _frame(at_ts: int) -> dict:
    from scoring.zone_score import (
        _signal_epoch,
        build_theatre,
        load_dark_vessels,
        rank_cues,
    )

    day = datetime.fromtimestamp(at_ts, timezone.utc).strftime("%Y-%m-%d")
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
