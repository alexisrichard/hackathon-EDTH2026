"""Query-parameter models for the time-window + bbox endpoints.

FastAPI binds these as query parameters via ``Depends``. The ``bbox`` is parsed
from a comma-separated ``min_lon,min_lat,max_lon,max_lat`` string (the wire form
the frontend sends) into a typed tuple, and validated against
``BALTIC_BBOX`` for sanity.

Conventions: coords ``[lon, lat]`` EPSG:4326, times ISO-8601 UTC.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, Query
from pydantic import BaseModel, Field, model_validator

# [min_lon, min_lat, max_lon, max_lat]
BBox = tuple[float, float, float, float]


def parse_bbox(raw: str | None) -> BBox | None:
    """Parse a ``"min_lon,min_lat,max_lon,max_lat"`` string into a BBox tuple.

    Returns None for an empty/None input (meaning "no spatial filter"). Raises
    ``ValueError`` on a malformed string so FastAPI returns a 422.
    """
    if raw is None or raw.strip() == "":
        return None
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be 'min_lon,min_lat,max_lon,max_lat' (4 numbers)")
    try:
        min_lon, min_lat, max_lon, max_lat = (float(p) for p in parts)
    except ValueError as exc:  # noqa: F841
        raise ValueError("bbox components must be numbers") from None
    if min_lon > max_lon or min_lat > max_lat:
        raise ValueError("bbox min must be <= max for both lon and lat")
    return (min_lon, min_lat, max_lon, max_lat)


class TimeWindowQuery(BaseModel):
    """A ``[start, end]`` time window (used by ``/vessels``)."""

    bbox: BBox | None = Field(None, description="Spatial filter [min_lon,min_lat,max_lon,max_lat].")
    start: datetime | None = Field(None, description="Window start, ISO-8601 UTC.")
    end: datetime | None = Field(None, description="Window end, ISO-8601 UTC.")
    limit: int = Field(500, ge=1, le=20000, description="Max vessels to return.")

    @model_validator(mode="after")
    def _check_order(self) -> "TimeWindowQuery":
        if self.start and self.end and self.start > self.end:
            raise ValueError("start must be <= end")
        return self


class TimeQuery(BaseModel):
    """A single instant ``t`` (used by ``/scores``, ``/cues``, ``/geo``)."""

    bbox: BBox | None = Field(None, description="Spatial filter [min_lon,min_lat,max_lon,max_lat].")
    t: datetime | None = Field(None, description="Evaluation instant, ISO-8601 UTC.")


# ---- FastAPI dependency wrappers ------------------------------------------------
# These produce the validated models above from raw query params. Kept thin so the
# routers stay declarative.


def time_window_params(
    bbox: str | None = Query(
        None, description="min_lon,min_lat,max_lon,max_lat (EPSG:4326)", examples=["25.5,59.6,27.0,60.4"]
    ),
    start: datetime | None = Query(None, description="ISO-8601 UTC start"),
    end: datetime | None = Query(None, description="ISO-8601 UTC end"),
    limit: int = Query(500, ge=1, le=20000, description="Max vessels"),
) -> TimeWindowQuery:
    """FastAPI dependency: build a validated :class:`TimeWindowQuery`."""
    try:
        return TimeWindowQuery(bbox=parse_bbox(bbox), start=start, end=end, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None


def time_params(
    bbox: str | None = Query(
        None, description="min_lon,min_lat,max_lon,max_lat (EPSG:4326)", examples=["25.5,59.6,27.0,60.4"]
    ),
    t: datetime | None = Query(None, description="ISO-8601 UTC instant"),
) -> TimeQuery:
    """FastAPI dependency: build a validated :class:`TimeQuery`."""
    try:
        return TimeQuery(bbox=parse_bbox(bbox), t=t)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
