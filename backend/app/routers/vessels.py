"""`/vessels` — vessel tracks in a bbox + time window (AIS replay)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.data import DataSource
from app.models.query import TimeWindowQuery, time_window_params
from app.models.responses import VesselsResponse
from app.routers.deps import data_source

router = APIRouter(tags=["vessels"])


@router.get("/vessels", response_model=VesselsResponse, summary="Vessel tracks in bbox + window")
def get_vessels(
    q: TimeWindowQuery = Depends(time_window_params),
    ds: DataSource = Depends(data_source),
) -> VesselsResponse:
    """Return vessel tracks (identity + ordered positions) within the bbox and
    ``[start, end]`` window. In mock mode, returns the scripted Eagle S fleet."""
    tracks = ds.vessel_tracks(bbox=q.bbox, start=q.start, end=q.end, limit=q.limit)
    return VesselsResponse(vessels=tracks)
