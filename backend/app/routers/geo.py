"""`/geo` — the criticality + cueing grid layer for the map overlays."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.data import DataSource
from app.models.query import TimeQuery, time_params
from app.models.responses import GeoResponse
from app.routers.deps import data_source

router = APIRouter(prefix="/geo", tags=["geo"])


@router.get("/criticality", response_model=GeoResponse, summary="Criticality + cueing grid at t")
def get_criticality(
    q: TimeQuery = Depends(time_params),
    ds: DataSource = Depends(data_source),
) -> GeoResponse:
    """Return the criticality grid at instant ``t``: per-cell static
    ``criticality`` (the heatmap overlay) and dynamic ``cue_score`` (drives the
    satellite-recommendation overlay)."""
    grid = ds.criticality_grid(t=q.t, bbox=q.bbox)
    return GeoResponse(grid=grid)
