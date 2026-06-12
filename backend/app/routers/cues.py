"""`/cues` — the product: ranked task-next ISR recommendations at instant t."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.data import DataSource
from app.models.query import TimeQuery, time_params
from app.models.responses import CuesResponse
from app.routers.deps import data_source

router = APIRouter(tags=["cues"])


@router.get("/cues", response_model=CuesResponse, summary="Top-N areas to task next")
def get_cues(
    q: TimeQuery = Depends(time_params),
    top: int = Query(5, ge=1, le=50, description="How many recommendations to return."),
    ds: DataSource = Depends(data_source),
) -> CuesResponse:
    """Return the top-``top`` ranked (area, time, sensor) recommendations at ``t``,
    each with the driver vessels and a human justification."""
    cues = ds.cues_at(t=q.t, top=top, bbox=q.bbox)
    # Echo the evaluated instant (matches the per-cue t and the /scores echo).
    when = q.t or (cues[0].t if cues else None)
    return CuesResponse(t=when, cues=cues)
