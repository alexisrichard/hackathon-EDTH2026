"""Geospatial criticality & cueing models — the per-area side of the engine.

The criticality surface (PLAN §5.2) is a grid of cells, each with a strategic
``criticality`` (static, from infrastructure layers) and a ``cue_score``
(dynamic, = criticality blended with the suspicion of the vessels currently in
the cell). Ranked cells become :class:`CueRecommendation`s — the actual product
(PLAN §5.5): a ranked "task-next" queue of (area, time, recommended sensor).

A cell's geometry is expressed as a bbox ``[min_lon, min_lat, max_lon, max_lat]``
(EPSG:4326). We also carry an optional ``h3`` index so a hex-grid frontend
(deck.gl H3HexagonLayer) can render directly; the grid scheme is intentionally
left flexible (frontend-plan §7 lists hex-vs-degree as an open question).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import SensorType

# A bbox is [min_lon, min_lat, max_lon, max_lat], EPSG:4326. Coords are [lon, lat].
BBox = tuple[float, float, float, float]


class GridCell(BaseModel):
    """One cell of the criticality / cueing grid at a given time."""

    cell_id: str = Field(..., description="Stable cell identifier (e.g. 'r12c34' or an H3 token).")
    bbox: BBox = Field(
        ..., description="Cell extent [min_lon, min_lat, max_lon, max_lat] (EPSG:4326)."
    )
    h3: str | None = Field(
        None, description="Optional H3 index if the grid is hex-based (else None)."
    )
    criticality: float = Field(
        ..., ge=0, le=1,
        description="Static strategic importance of this cell (1 = over a cable/base).",
    )
    cue_score: float = Field(
        ..., ge=0, le=1,
        description="Dynamic value-of-tasking score: criticality blended with in-cell suspicion.",
    )
    driver_mmsis: list[int] = Field(
        default_factory=list,
        description="MMSIs of the vessels currently driving this cell's cue_score.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "cell_id": "estlink2-hot",
                "bbox": [26.2, 59.85, 26.6, 60.15],
                "h3": None,
                "criticality": 0.94,
                "cue_score": 0.91,
                "driver_mmsis": [372985000],
            }
        }
    }


class CueRecommendation(BaseModel):
    """A ranked ISR-tasking recommendation — the engine's actual output (PLAN §5.5).

    "Point a *sensor* at *this box* at *this time*, here's *why* and *who* is
    driving it." Ranked by ``score`` (highest = task first).
    """

    rank: int = Field(..., ge=1, description="1-based priority rank (1 = task first).")
    cell_id: str | None = Field(
        None, description="Originating grid cell id, if the cue came from a single cell."
    )
    bbox: BBox = Field(
        ..., description="Recommended area to task [min_lon, min_lat, max_lon, max_lat]."
    )
    t: datetime = Field(..., description="Time the recommendation applies to (UTC).")
    sensor: SensorType = Field(..., description="Recommended sensor to task.")
    score: float = Field(
        ..., ge=0, le=1, description="Expected value of a sensor pass here (0–1)."
    )
    driver_mmsis: list[int] = Field(
        default_factory=list,
        description="MMSIs of the vessels justifying this recommendation.",
    )
    why: str = Field("", description="Human-readable justification.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "rank": 1,
                "cell_id": "estlink2-hot",
                "bbox": [26.2, 59.85, 26.6, 60.15],
                "t": "2024-12-25T14:00:00Z",
                "sensor": "SAR",
                "score": 0.93,
                "driver_mmsis": [372985000],
                "why": "Tanker EAGLE S loitering at 2 kn directly over Estlink 2; AIS gap 41 min.",
            }
        }
    }


class CriticalityGrid(BaseModel):
    """The full criticality / cueing grid at a moment in time.

    Returned by ``/geo/criticality`` so the frontend can draw the heatmap overlay
    (frontend-plan §3 overlay #1) and the cueing overlay (#3) from one payload.
    """

    t: datetime = Field(..., description="Time the grid is evaluated at (UTC).")
    bbox: BBox = Field(..., description="Overall extent covered by the grid.")
    cells: list[GridCell] = Field(default_factory=list, description="Grid cells.")
